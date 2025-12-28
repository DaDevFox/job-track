"""Textual app for managing job applications."""

from __future__ import annotations

import os
import webbrowser
from dataclasses import dataclass
from typing import Optional

import httpx
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

API_URL = os.getenv("JOBTRACK_API_URL", "http://127.0.0.1:8787/api")
VIEW_HISTORY = "history"
VIEW_SCRAPED = "scraped"


@dataclass
class JobRow:
    id: str
    title: str
    company: str
    location: Optional[str]
    description: Optional[str]
    apply_url: str
    tags: list[str]
    new_grad: bool
    is_applied: bool
    pending_since: Optional[str]
    profile_used_id: Optional[str]
    origin: str = VIEW_HISTORY

    @property
    def status_label(self) -> str:
        if self.origin == VIEW_SCRAPED:
            return "Applied" if self.is_applied else "Scraped"
        if self.is_applied:
            return "Applied"
        if self.pending_since:
            return "Pending"
        return "Open"


class JobClient:
    """Thin wrapper around the REST API for the TUI."""

    def __init__(self, base_url: str = API_URL):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=15)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_jobs(self, *, new_grad_only: bool, only_unapplied: bool) -> list[JobRow]:
        response = await self._client.get(
            "/jobs",
            params={
                "new_grad_only": str(new_grad_only).lower(),
                "only_unapplied": str(only_unapplied).lower(),
            },
        )
        response.raise_for_status()
        rows = []
        for job in response.json():
            rows.append(
                JobRow(
                    id=job["id"],
                    title=job["title"],
                    company=job["company"],
                    location=job.get("location"),
                    description=job.get("description"),
                    apply_url=job["apply_url"],
                    tags=job.get("tags", []),
                    new_grad=job.get("new_grad", False),
                    is_applied=job.get("is_applied", False),
                    pending_since=job.get("pending_since"),
                    profile_used_id=job.get("profile_used_id"),
                    origin=VIEW_HISTORY,
                )
            )
        return rows

    async def fetch_scraped_jobs(self, *, new_grad_only: bool, include_applied: bool) -> list[JobRow]:
        response = await self._client.get(
            "/scraped",
            params={
                "new_grad_only": str(new_grad_only).lower(),
                "include_applied": str(include_applied).lower(),
            },
        )
        response.raise_for_status()
        rows = []
        for job in response.json():
            rows.append(
                JobRow(
                    id=job["id"],
                    title=job["title"],
                    company=job["company"],
                    location=job.get("location"),
                    description=job.get("description"),
                    apply_url=job["apply_url"],
                    tags=job.get("tags", []),
                    new_grad=job.get("new_grad", False),
                    is_applied=job.get("applied", False),
                    pending_since=None,
                    profile_used_id=None,
                    origin=VIEW_SCRAPED,
                )
            )
        return rows

    async def set_pending(self, job_id: str, pending: bool) -> None:
        response = await self._client.post(f"/jobs/{job_id}/pending", json={"pending": pending})
        response.raise_for_status()

    async def mark_applied(self, job_id: str, profile_id: Optional[str]) -> None:
        response = await self._client.post(
            f"/jobs/{job_id}/applied",
            json={"profile_id": profile_id, "mark_applied": True},
        )
        response.raise_for_status()

    async def fetch_profiles(self) -> list[dict]:
        response = await self._client.get("/profiles")
        response.raise_for_status()
        return response.json()

    async def scrape_jobs(self, payload: dict, *, clear_existing: bool = True) -> dict:
        response = await self._client.post(
            "/scraped/refresh",
            params={"clear_existing": str(clear_existing).lower()},
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def apply_scraped_job(self, scraped_id: str, profile_id: Optional[str]) -> dict:
        response = await self._client.post(
            f"/scraped/{scraped_id}/apply",
            json={"profile_id": profile_id, "notes": None},
        )
        response.raise_for_status()
        return response.json()


class JobTable(DataTable):
    """Table widget that holds job rows."""

    def __init__(self) -> None:
        super().__init__(zebra_stripes=True)
        self.cursor_type = "row"
        self.can_focus = True
        self.add_columns("Title", "Company", "Location", "Tags", "Status")
        self._row_lookup: list[JobRow] = []

    def update_rows(self, jobs: list[JobRow]) -> None:
        self.clear()
        self._row_lookup = list(jobs)
        for job in jobs:
            self.add_row(
                job.title,
                job.company,
                job.location or "-",
                ", ".join(job.tags) if job.tags else "",
                job.status_label,
            )
        if jobs:
            self.cursor_coordinate = (0, 0)

    def current_job(self) -> Optional[JobRow]:
        if self.cursor_row is None:
            return None
        if 0 <= self.cursor_row < len(self._row_lookup):
            return self._row_lookup[self.cursor_row]
        return None


class ProfileSelectScreen(ModalScreen[Optional[str]]):
    """Modal that lets the user choose which profile they used."""

    class Submitted(Message):
        def __init__(self, profile_id: Optional[str]):
            self.profile_id = profile_id
            super().__init__()

    def __init__(self, profiles: list[dict]):
        super().__init__()
        self._profiles = profiles

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Select profile used for this application", classes="modal-title"),
            OptionList(
                Option("Skip (no profile)", None),
                *[Option(f"{prof['label']} — {prof['full_name']}", prof["id"]) for prof in self._profiles],
                id="profile-options",
            ),
            Button("Cancel", id="cancel", variant="error"),
            classes="modal-body",
        )

    @on(OptionList.OptionSelected)
    def option_chosen(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.value)

    @on(Button.Pressed)
    def cancel(self, event: Button.Pressed) -> None:  # pragma: no cover - user interaction
        if event.button.id == "cancel":
            self.dismiss(None)


class ScrapeFormScreen(ModalScreen[Optional[dict]]):
    """Modal for specifying scrape parameters."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Trigger scraping run", classes="modal-title"),
            Input(placeholder="Company name", id="company"),
            Input(placeholder="Job board URL", id="url"),
            Input(value="generic", placeholder="Source (generic/lever/...)", id="source"),
            Checkbox(label="New grad only", value=False, id="new-grad"),
            Input(value="25", placeholder="Max jobs to keep", id="limit"),
            Checkbox(label="Replace existing scraped list", value=True, id="clear-existing"),
            Static("", id="scrape-status"),
            Container(
                Button("Start", id="start", variant="primary"),
                Button("Cancel", id="cancel", variant="error"),
            ),
            classes="modal-body",
        )

    def gather_payload(self) -> Optional[dict]:
        status = self.query_one("#scrape-status", Static)
        company = self.query_one("#company", Input).value.strip()
        url = self.query_one("#url", Input).value.strip()
        source = self.query_one("#source", Input).value.strip() or "generic"
        limit_text = self.query_one("#limit", Input).value.strip() or "25"
        if not company or not url:
            status.update("Company and URL required")
            return None
        try:
            limit = max(1, int(limit_text))
        except ValueError:
            status.update("Limit must be numeric")
            return None
        return {
            "company": company,
            "url": url,
            "source": source,
            "new_grad_only": self.query_one("#new-grad", Checkbox).value,
            "limit": limit,
            "clear_existing": self.query_one("#clear-existing", Checkbox).value,
        }

    @on(Button.Pressed)
    def handle_buttons(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        payload = self.gather_payload()
        if payload:
            self.dismiss(payload)


class JobTrackApp(App):
    """Main Textual application."""

    CSS = """
    Screen {
        align: center top;
    }
    #jobs {
        height: 1fr;
    }
    #status {
        padding: 1 1;
    }
    .modal-body {
        padding: 1 2;
        border: round $primary;
        width: 60%;
        margin: 1 2;
    }
    .modal-title {
        padding-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("n", "toggle_new_grad", "Toggle new grad"),
        Binding("u", "toggle_unapplied", "Toggle unapplied"),
        Binding("s", "toggle_view", "Scraped/history"),
        Binding("enter", "open_job", "Open apply link"),
        Binding("a", "mark_applied", "Mark applied"),
        Binding("g", "trigger_scrape", "Scrape jobs"),
    ]

    jobs: reactive[list[JobRow]] = reactive([])

    def __init__(self) -> None:
        super().__init__()
        self.client = JobClient()
        self.new_grad_only = True
        self.only_unapplied = True
        self.view_mode = VIEW_SCRAPED

    def compose(self) -> ComposeResult:
        yield Header()
        table = JobTable()
        table.id = "jobs"
        yield table
        yield Static("", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_jobs()

    async def on_unmount(self) -> None:  # pragma: no cover - application shutdown
        await self.client.close()

    def status(self, message: str) -> None:
        widget = self.query_one("#status", Static)
        widget.update(Text(message))

    async def refresh_jobs(self) -> None:
        try:
            if self.view_mode == VIEW_SCRAPED:
                include_applied = not self.only_unapplied
                jobs = await self.client.fetch_scraped_jobs(
                    new_grad_only=self.new_grad_only,
                    include_applied=include_applied,
                )
            else:
                jobs = await self.client.fetch_jobs(
                    new_grad_only=self.new_grad_only,
                    only_unapplied=self.only_unapplied,
                )
        except httpx.HTTPError as exc:
            self.status(f"API offline? {exc}")
            return
        self.jobs = jobs
        self.query_one(JobTable).update_rows(jobs)
        if self.view_mode == VIEW_SCRAPED:
            include_applied = not self.only_unapplied
            self.status(
                f"[scraped] Loaded {len(jobs)} rows | new_grad_only={self.new_grad_only} | include_applied={include_applied}"
            )
        else:
            self.status(
                f"[history] Loaded {len(jobs)} rows | new_grad_only={self.new_grad_only} | only_unapplied={self.only_unapplied}"
            )

    async def action_refresh(self) -> None:
        await self.refresh_jobs()

    async def action_toggle_new_grad(self) -> None:
        self.new_grad_only = not self.new_grad_only
        await self.refresh_jobs()

    async def action_toggle_unapplied(self) -> None:
        self.only_unapplied = not self.only_unapplied
        await self.refresh_jobs()

    async def action_toggle_view(self) -> None:
        self.view_mode = VIEW_HISTORY if self.view_mode == VIEW_SCRAPED else VIEW_SCRAPED
        await self.refresh_jobs()

    async def action_open_job(self) -> None:
        job = self.query_one(JobTable).current_job()
        if not job:
            return
        if self.view_mode == VIEW_HISTORY:
            try:
                await self.client.set_pending(job.id, True)
            except httpx.HTTPError as exc:
                self.status(f"Failed to mark pending: {exc}")
                return
            webbrowser.open(job.apply_url)
            self.status(f"Opened {job.title}. Press 'a' when you finish applying.")
            return

        webbrowser.open(job.apply_url)
        self.status("Opened scraped listing. Use 'a' to log it once applied.")

    async def action_mark_applied(self) -> None:
        job = self.query_one(JobTable).current_job()
        if not job:
            return
        if self.view_mode == VIEW_SCRAPED:
            await self._log_scraped_application(job)
        else:
            await self._mark_history_application(job)

    def action_trigger_scrape(self) -> None:
        self.run_worker(self._scrape_flow(), exclusive=True, thread=False, name="scrape-flow")

    async def _scrape_flow(self) -> None:
        payload = await self.push_screen_wait(ScrapeFormScreen())
        if not payload:
            return
        payload = dict(payload)
        clear_existing = payload.pop("clear_existing", True)
        total_steps = 4
        self._scrape_progress("Validating form", 1, total_steps)
        try:
            self._scrape_progress("Running scraper", 2, total_steps)
            result = await self.client.scrape_jobs(payload, clear_existing=clear_existing)
        except httpx.HTTPError as exc:
            detail = self._http_error_detail(exc)
            self._scrape_progress("Scrape failed", total_steps, total_steps)
            self.status(f"Scrape failed: {detail}")
            return
        self._scrape_progress("Refreshing scraped table", 3, total_steps)
        self.view_mode = VIEW_SCRAPED
        await self.refresh_jobs()
        inserted = result.get("inserted") if isinstance(result, dict) else None
        fetched = len(result.get("jobs", [])) if isinstance(result, dict) else None
        summary = (
            f"Scrape complete: inserted {inserted or 0} of {fetched or 'unknown'}"
            f" | clear_existing={clear_existing}"
        )
        if fetched and inserted is not None and fetched > inserted:
            summary += f" ({fetched - inserted} duplicates skipped)"
        self._scrape_progress("Done", total_steps, total_steps)
        self.status(summary)

    def _scrape_progress(self, label: str, step: int, total: int) -> None:
        total = max(1, total)
        step = max(0, min(step, total))
        filled = int((step / total) * 10)
        bar = f"[{'#' * filled}{'-' * (10 - filled)}]"
        self.status(f"Scrape {bar} {label}")

    def _http_error_detail(self, exc: httpx.HTTPError) -> str:
        response = getattr(exc, "response", None)
        if response is None:
            return str(exc)
        try:
            data = response.json()
            if isinstance(data, dict) and "detail" in data:
                return f"{response.status_code}: {data['detail']}"
            if isinstance(data, dict):
                return f"{response.status_code}: {data}"
        except ValueError:
            pass
        text = response.text.strip()
        return f"{response.status_code}: {text or exc}"

    async def _prompt_profile_selection(self) -> tuple[Optional[str], bool]:
        try:
            profiles = await self.client.fetch_profiles()
        except httpx.HTTPError as exc:
            self.status(f"Failed to fetch profiles: {exc}")
            return None, False
        if not profiles:
            return None, False
        selection = await self.push_screen_wait(ProfileSelectScreen(profiles))
        return selection, True

    async def _mark_history_application(self, job: JobRow) -> None:
        if job.is_applied:
            self.status("Already marked as applied in history view.")
            return
        profile_id, had_profiles = await self._prompt_profile_selection()
        if profile_id is None and had_profiles:
            self.status("Marked without profile. Use extension for richer data.")
        try:
            await self.client.mark_applied(job.id, profile_id)
        except httpx.HTTPError as exc:
            self.status(f"Failed to mark applied: {exc}")
            return
        await self.refresh_jobs()
        self.status(f"Marked {job.title} as applied.")

    async def _log_scraped_application(self, job: JobRow) -> None:
        if job.is_applied:
            self.status("Already logged from scraped table.")
            return
        profile_id, had_profiles = await self._prompt_profile_selection()
        if profile_id is None and had_profiles:
            self.status("Logging without profile selection.")
        try:
            await self.client.apply_scraped_job(job.id, profile_id)
        except httpx.HTTPError as exc:
            self.status(f"Failed to log scraped job: {exc}")
            return
        await self.refresh_jobs()
        self.status(f"Logged application for {job.title} from scraped list.")


if __name__ == "__main__":
    app = JobTrackApp()
    app.run()
