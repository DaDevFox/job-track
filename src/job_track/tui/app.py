"""Textual TUI application for job-track.

This provides a terminal-based user interface for:
- Viewing job listings
- Filtering jobs (new-grad, applied, etc.)
- Opening job links in browser
- Marking jobs as applied
- Managing profiles
"""

import datetime
import webbrowser
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    Switch,
)

from job_track.db.models import Job, Profile, get_session, init_db


class ConfirmApplyScreen(ModalScreen[bool]):
    """Modal dialog to confirm if user applied to a job."""

    CSS = """
    ConfirmApplyScreen {
        align: center middle;
    }

    #dialog {
        width: 60;
        height: 12;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #question {
        text-align: center;
        margin-bottom: 1;
    }

    #buttons {
        align: center middle;
        height: 3;
    }

    Button {
        margin: 0 2;
    }
    """

    def __init__(self, job_title: str, company: str):
        """Initialize with job info."""
        super().__init__()
        self.job_title = job_title
        self.company = company

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="dialog"):
            yield Label("Did you apply?", id="question")
            yield Label(f"Job: {self.job_title}", classes="job-info")
            yield Label(f"Company: {self.company}", classes="job-info")
            with Horizontal(id="buttons"):
                yield Button("Yes, Applied", id="yes", variant="success")
                yield Button("No", id="no", variant="error")

    @on(Button.Pressed, "#yes")
    def confirm_yes(self) -> None:
        """User confirmed they applied."""
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def confirm_no(self) -> None:
        """User did not apply."""
        self.dismiss(False)


class JobDetailScreen(ModalScreen[None]):
    """Modal screen showing job details."""

    CSS = """
    JobDetailScreen {
        align: center middle;
    }

    #detail-container {
        width: 80%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #detail-scroll {
        height: 100%;
    }

    .detail-label {
        color: $primary;
        text-style: bold;
    }

    .detail-value {
        margin-bottom: 1;
    }

    #detail-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    def __init__(self, job: dict):
        """Initialize with job data."""
        super().__init__()
        self.job = job

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="detail-container"):
            with VerticalScroll(id="detail-scroll"):
                yield Label("Title:", classes="detail-label")
                yield Label(self.job.get("title", "N/A"), classes="detail-value")

                yield Label("Company:", classes="detail-label")
                yield Label(self.job.get("company", "N/A"), classes="detail-value")

                yield Label("Location:", classes="detail-label")
                yield Label(self.job.get("location") or "Not specified", classes="detail-value")

                yield Label("Tags:", classes="detail-label")
                tags = self.job.get("tags", [])
                yield Label(", ".join(tags) if tags else "None", classes="detail-value")

                yield Label("Apply URL:", classes="detail-label")
                yield Label(self.job.get("apply_url", "N/A"), classes="detail-value")

                yield Label("Description:", classes="detail-label")
                desc = self.job.get("description") or "No description available"
                yield Label(desc[:2000] if len(desc) > 2000 else desc, classes="detail-value")

            with Horizontal(id="detail-buttons"):
                yield Button("Open Link", id="open-link", variant="primary")
                yield Button("Close", id="close", variant="default")

    @on(Button.Pressed, "#open-link")
    def open_link(self) -> None:
        """Open the job link in browser."""
        url = self.job.get("apply_url")
        if url:
            webbrowser.open(url)

    @on(Button.Pressed, "#close")
    def close_dialog(self) -> None:
        """Close the dialog."""
        self.dismiss(None)


class ProfileSelectScreen(ModalScreen[Optional[str]]):
    """Modal screen for selecting a profile."""

    CSS = """
    ProfileSelectScreen {
        align: center middle;
    }

    #profile-container {
        width: 60;
        height: 20;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #profile-list {
        height: 1fr;
    }

    #profile-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    def __init__(self):
        """Initialize."""
        super().__init__()
        self.profiles = []
        self.selected_profile_id = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="profile-container"):
            yield Label("Select Profile for Application")
            with VerticalScroll(id="profile-list"):
                session = get_session()
                try:
                    self.profiles = session.query(Profile).all()
                    for profile in self.profiles:
                        yield Button(
                            f"{profile.name} ({profile.email})",
                            id=f"profile-{profile.id}",
                            classes="profile-btn",
                        )
                finally:
                    session.close()
            with Horizontal(id="profile-buttons"):
                yield Button("Cancel", id="cancel", variant="default")

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id and event.button.id.startswith("profile-"):
            profile_id = event.button.id.replace("profile-", "")
            self.dismiss(profile_id)


class AddProfileScreen(ModalScreen[None]):
    """Modal screen for adding a new profile."""

    CSS = """
    AddProfileScreen {
        align: center middle;
    }

    #add-profile-container {
        width: 60;
        height: 25;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    .field-label {
        margin-top: 1;
    }

    Input {
        margin-bottom: 1;
    }

    #add-profile-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="add-profile-container"):
            yield Label("Add New Profile", id="add-title")
            yield Label("Name:", classes="field-label")
            yield Input(id="name-input", placeholder="Full Name")
            yield Label("Email:", classes="field-label")
            yield Input(id="email-input", placeholder="email@example.com")
            yield Label("Phone:", classes="field-label")
            yield Input(id="phone-input", placeholder="+1-555-555-5555")
            yield Label("LinkedIn URL:", classes="field-label")
            yield Input(id="linkedin-input", placeholder="https://linkedin.com/in/...")
            with Horizontal(id="add-profile-buttons"):
                yield Button("Save", id="save", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    @on(Button.Pressed, "#save")
    def save_profile(self) -> None:
        """Save the new profile."""
        name = self.query_one("#name-input", Input).value
        email = self.query_one("#email-input", Input).value
        phone = self.query_one("#phone-input", Input).value
        linkedin = self.query_one("#linkedin-input", Input).value

        if not name or not email:
            return  # Basic validation

        session = get_session()
        try:
            profile = Profile(
                name=name,
                email=email,
                phone=phone if phone else None,
                linkedin_url=linkedin if linkedin else None,
            )
            session.add(profile)
            session.commit()
        finally:
            session.close()

        self.dismiss(None)

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(None)


class JobTrackApp(App):
    """Main TUI application for job tracking."""

    CSS = """
    #main-container {
        height: 100%;
    }

    #filter-bar {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    #filter-bar Horizontal {
        height: 100%;
        align: left middle;
    }

    #filter-bar Label {
        margin-right: 1;
    }

    #filter-bar Switch {
        margin-right: 2;
    }

    #filter-bar Input {
        width: 30;
    }

    #job-table {
        height: 1fr;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }

    DataTable {
        height: 100%;
    }

    DataTable > .datatable--cursor {
        background: $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "open_job", "Open/Apply"),
        Binding("d", "view_details", "Details"),
        Binding("a", "mark_applied", "Mark Applied"),
        Binding("p", "select_profile", "Profiles"),
        Binding("n", "add_profile", "New Profile"),
        Binding("f", "toggle_filter", "Toggle Filters"),
        Binding("/", "search", "Search"),
    ]

    def __init__(self):
        """Initialize the app."""
        super().__init__()
        self.jobs: list[dict] = []
        self.current_filter = "all"  # all, new-grad, applied, pending
        self.search_term = ""
        self.selected_profile_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        with Container(id="main-container"):
            with Horizontal(id="filter-bar"):
                yield Label("Filters:")
                yield Switch(id="new-grad-filter")
                yield Label("New Grad")
                yield Switch(id="applied-filter")
                yield Label("Applied")
                yield Switch(id="pending-filter")
                yield Label("Pending")
                yield Input(id="search-input", placeholder="Search...")
            yield DataTable(id="job-table")
            yield Static("Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        init_db()
        table = self.query_one(DataTable)
        table.add_columns("Company", "Title", "Location", "Tags", "Status")
        table.cursor_type = "row"
        self.refresh_jobs()

    def refresh_jobs(self) -> None:
        """Refresh job list from database."""
        session = get_session()
        try:
            query = session.query(Job)

            # Apply filters
            new_grad_filter = self.query_one("#new-grad-filter", Switch).value
            applied_filter = self.query_one("#applied-filter", Switch).value
            pending_filter = self.query_one("#pending-filter", Switch).value
            search_input = self.query_one("#search-input", Input).value

            if new_grad_filter:
                query = query.filter(Job.tags.contains('"new-grad"'))
            if applied_filter:
                query = query.filter(Job.is_applied == True)  # noqa: E712
            if pending_filter:
                query = query.filter(Job.is_pending == True)  # noqa: E712
            if search_input:
                term = f"%{search_input}%"
                query = query.filter(
                    (Job.title.ilike(term))
                    | (Job.company.ilike(term))
                    | (Job.description.ilike(term))
                )

            jobs = query.order_by(Job.scraped_at.desc()).limit(500).all()
            self.jobs = [job.to_dict() for job in jobs]

            # Update table
            table = self.query_one(DataTable)
            table.clear()
            for job in self.jobs:
                status = ""
                if job["is_applied"]:
                    status = "✓ Applied"
                elif job["is_pending"]:
                    status = "⏳ Pending"

                tags = ", ".join(job.get("tags", []))[:20]
                table.add_row(
                    job["company"][:25],
                    job["title"][:40],
                    (job.get("location") or "")[:20],
                    tags,
                    status,
                    key=job["id"],
                )

            self.update_status(f"Loaded {len(self.jobs)} jobs")
        finally:
            session.close()

    def update_status(self, message: str) -> None:
        """Update status bar message."""
        status = self.query_one("#status-bar", Static)
        status.update(message)

    def get_selected_job(self) -> Optional[dict]:
        """Get the currently selected job."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.jobs):
            return self.jobs[table.cursor_row]
        return None

    @on(Switch.Changed)
    def filter_changed(self) -> None:
        """Handle filter switch changes."""
        self.refresh_jobs()

    @on(Input.Submitted, "#search-input")
    def search_submitted(self) -> None:
        """Handle search input submission."""
        self.refresh_jobs()

    def action_refresh(self) -> None:
        """Refresh job list."""
        self.refresh_jobs()

    def action_open_job(self) -> None:
        """Open job link in browser and mark as pending."""
        job = self.get_selected_job()
        if not job:
            self.update_status("No job selected")
            return

        url = job.get("apply_url")
        if url:
            # Mark as pending
            session = get_session()
            try:
                db_job = session.query(Job).filter(Job.id == job["id"]).first()
                if db_job:
                    db_job.is_pending = True
                    session.commit()
            finally:
                session.close()

            # Open in browser
            webbrowser.open(url)
            self.update_status(f"Opened: {job['title']} - Mark as applied when done (press 'a')")
            self.refresh_jobs()

    def action_view_details(self) -> None:
        """Show job details."""
        job = self.get_selected_job()
        if job:
            self.push_screen(JobDetailScreen(job))

    async def action_mark_applied(self) -> None:
        """Mark job as applied with confirmation dialog."""
        job = self.get_selected_job()
        if not job:
            self.update_status("No job selected")
            return

        # Show confirmation dialog
        applied = await self.push_screen_wait(
            ConfirmApplyScreen(job["title"], job["company"])
        )

        session = get_session()
        try:
            db_job = session.query(Job).filter(Job.id == job["id"]).first()
            if db_job:
                db_job.is_pending = False
                if applied:
                    db_job.is_applied = True
                    db_job.applied_at = datetime.datetime.now()
                    if self.selected_profile_id:
                        db_job.profile_id = self.selected_profile_id
                    self.update_status(f"Marked as applied: {job['title']}")
                else:
                    self.update_status(f"Not applied: {job['title']}")
                session.commit()
        finally:
            session.close()

        self.refresh_jobs()

    async def action_select_profile(self) -> None:
        """Select a profile for applications."""
        profile_id = await self.push_screen_wait(ProfileSelectScreen())
        if profile_id:
            self.selected_profile_id = profile_id
            session = get_session()
            try:
                profile = session.query(Profile).filter(Profile.id == profile_id).first()
                if profile:
                    self.update_status(f"Selected profile: {profile.name}")
            finally:
                session.close()

    async def action_add_profile(self) -> None:
        """Add a new profile."""
        await self.push_screen_wait(AddProfileScreen())
        self.update_status("Profile added")

    def action_toggle_filter(self) -> None:
        """Toggle between filter presets."""
        # Cycle through: all -> new-grad -> applied -> pending -> all
        new_grad = self.query_one("#new-grad-filter", Switch)
        applied = self.query_one("#applied-filter", Switch)
        pending = self.query_one("#pending-filter", Switch)

        if not any([new_grad.value, applied.value, pending.value]):
            new_grad.value = True
            self.current_filter = "new-grad"
        elif new_grad.value and not applied.value:
            new_grad.value = False
            applied.value = True
            self.current_filter = "applied"
        elif applied.value:
            applied.value = False
            pending.value = True
            self.current_filter = "pending"
        else:
            pending.value = False
            self.current_filter = "all"

    def action_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()


def main():
    """Run the TUI application."""
    app = JobTrackApp()
    app.run()


if __name__ == "__main__":
    main()
