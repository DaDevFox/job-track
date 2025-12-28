"""Textual TUI application for job-track.

This provides a terminal-based user interface for:
- Viewing job listings (from API and scraping)
- Filtering jobs (new-grad, applied, etc.)
- Opening job links in browser
- Marking jobs as applied
- Managing profiles with resumes
- Viewing application history
"""

import datetime
import webbrowser
from pathlib import Path
from typing import Optional

import httpx
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from job_track.db.models import Job, Profile, get_resume_dir, get_session, init_db


# ============================================================================
# Modal Screens
# ============================================================================


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

    def __init__(self, job_title: str, company: str) -> None:
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

    def key_escape(self) -> None:
        """Handle escape key."""
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

    def __init__(self, job: dict) -> None:
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

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(None)


class ProfileSelectScreen(ModalScreen[Optional[str]]):
    """Modal screen for selecting a profile."""

    CSS = """
    ProfileSelectScreen {
        align: center middle;
    }

    #profile-container {
        width: 70;
        height: 25;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #profile-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #profile-list {
        height: 1fr;
        margin-bottom: 1;
    }

    .profile-btn {
        width: 100%;
        margin-bottom: 1;
    }

    #profile-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="profile-container"):
            yield Label("Select Profile for Application", id="profile-title")
            with VerticalScroll(id="profile-list"):
                session = get_session()
                try:
                    profiles = session.query(Profile).all()
                    if profiles:
                        for profile in profiles:
                            resume_info = ""
                            latest = profile.get_latest_resume_version()
                            if latest:
                                resume_info = f" - Resume: {latest.get('name', 'N/A')}"
                            yield Button(
                                f"{profile.name} ({profile.email}){resume_info}",
                                id=f"profile-{profile.id}",
                                classes="profile-btn",
                            )
                    else:
                        yield Label("No profiles found. Create one first!")
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

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(None)


class ProfileEditScreen(ModalScreen[bool]):
    """Modal screen for creating or editing a profile."""

    CSS = """
    ProfileEditScreen {
        align: center middle;
    }

    #edit-profile-container {
        width: 80;
        height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #edit-profile-scroll {
        height: 1fr;
    }

    .field-label {
        margin-top: 1;
        color: $primary;
    }

    .section-header {
        margin-top: 2;
        text-style: bold;
        color: $secondary;
    }

    Input {
        margin-bottom: 0;
    }

    #edit-profile-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    def __init__(self, profile_id: Optional[str] = None) -> None:
        """Initialize with optional profile ID for editing."""
        super().__init__()
        self.profile_id = profile_id
        self.profile: Optional[Profile] = None
        if profile_id:
            session = get_session()
            try:
                self.profile = session.query(Profile).filter(Profile.id == profile_id).first()
            finally:
                session.close()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        title = "Edit Profile" if self.profile else "Add New Profile"
        with Vertical(id="edit-profile-container"):
            yield Label(title, id="edit-title")
            with VerticalScroll(id="edit-profile-scroll"):
                # Basic Info
                yield Label("── Basic Information ──", classes="section-header")
                yield Label("Name:", classes="field-label")
                yield Input(
                    id="name-input",
                    placeholder="Full Name",
                    value=self.profile.name if self.profile else "",
                )
                yield Label("Email:", classes="field-label")
                yield Input(
                    id="email-input",
                    placeholder="email@example.com",
                    value=self.profile.email if self.profile else "",
                )
                yield Label("Phone:", classes="field-label")
                yield Input(
                    id="phone-input",
                    placeholder="+1-555-555-5555",
                    value=self.profile.phone if self.profile and self.profile.phone else "",
                )

                # Address
                yield Label("── Address ──", classes="section-header")
                yield Label("Street Address:", classes="field-label")
                yield Input(
                    id="street-input",
                    placeholder="123 Main St",
                    value=self.profile.address_street if self.profile and self.profile.address_street else "",
                )
                yield Label("City:", classes="field-label")
                yield Input(
                    id="city-input",
                    placeholder="City",
                    value=self.profile.address_city if self.profile and self.profile.address_city else "",
                )
                yield Label("State/Province:", classes="field-label")
                yield Input(
                    id="state-input",
                    placeholder="State",
                    value=self.profile.address_state if self.profile and self.profile.address_state else "",
                )
                yield Label("ZIP/Postal Code:", classes="field-label")
                yield Input(
                    id="zip-input",
                    placeholder="12345",
                    value=self.profile.address_zip if self.profile and self.profile.address_zip else "",
                )
                yield Label("Country:", classes="field-label")
                yield Input(
                    id="country-input",
                    placeholder="USA",
                    value=self.profile.address_country if self.profile and self.profile.address_country else "",
                )

                # URLs
                yield Label("── Online Profiles ──", classes="section-header")
                yield Label("LinkedIn URL:", classes="field-label")
                yield Input(
                    id="linkedin-input",
                    placeholder="https://linkedin.com/in/...",
                    value=self.profile.linkedin_url if self.profile and self.profile.linkedin_url else "",
                )
                yield Label("GitHub URL:", classes="field-label")
                yield Input(
                    id="github-input",
                    placeholder="https://github.com/...",
                    value=self.profile.github_url if self.profile and self.profile.github_url else "",
                )
                yield Label("Portfolio URL:", classes="field-label")
                yield Input(
                    id="portfolio-input",
                    placeholder="https://portfolio.com",
                    value=self.profile.portfolio_url if self.profile and self.profile.portfolio_url else "",
                )

            with Horizontal(id="edit-profile-buttons"):
                yield Button("Save", id="save", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    @on(Button.Pressed, "#save")
    def save_profile(self) -> None:
        """Save the profile."""
        name = self.query_one("#name-input", Input).value.strip()
        email = self.query_one("#email-input", Input).value.strip()
        phone = self.query_one("#phone-input", Input).value.strip()
        street = self.query_one("#street-input", Input).value.strip()
        city = self.query_one("#city-input", Input).value.strip()
        state = self.query_one("#state-input", Input).value.strip()
        zip_code = self.query_one("#zip-input", Input).value.strip()
        country = self.query_one("#country-input", Input).value.strip()
        linkedin = self.query_one("#linkedin-input", Input).value.strip()
        github = self.query_one("#github-input", Input).value.strip()
        portfolio = self.query_one("#portfolio-input", Input).value.strip()

        if not name or not email:
            return  # Basic validation

        session = get_session()
        try:
            if self.profile_id:
                profile = session.query(Profile).filter(Profile.id == self.profile_id).first()
                if profile:
                    profile.name = name
                    profile.email = email
                    profile.phone = phone if phone else None
                    profile.address_street = street if street else None
                    profile.address_city = city if city else None
                    profile.address_state = state if state else None
                    profile.address_zip = zip_code if zip_code else None
                    profile.address_country = country if country else None
                    profile.linkedin_url = linkedin if linkedin else None
                    profile.github_url = github if github else None
                    profile.portfolio_url = portfolio if portfolio else None
            else:
                profile = Profile(
                    name=name,
                    email=email,
                    phone=phone if phone else None,
                    address_street=street if street else None,
                    address_city=city if city else None,
                    address_state=state if state else None,
                    address_zip=zip_code if zip_code else None,
                    address_country=country if country else None,
                    linkedin_url=linkedin if linkedin else None,
                    github_url=github if github else None,
                    portfolio_url=portfolio if portfolio else None,
                )
                session.add(profile)
            session.commit()
        finally:
            session.close()

        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(False)

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(False)


class ResumeUploadScreen(ModalScreen[bool]):
    """Modal screen for uploading a resume."""

    CSS = """
    ResumeUploadScreen {
        align: center middle;
    }

    #resume-container {
        width: 70;
        height: 20;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    .field-label {
        margin-top: 1;
        color: $primary;
    }

    Input {
        margin-bottom: 1;
    }

    #resume-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    #resume-info {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, profile_id: str) -> None:
        """Initialize with profile ID."""
        super().__init__()
        self.profile_id = profile_id

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="resume-container"):
            yield Label("Upload Resume", id="resume-title")
            yield Label("Enter the full path to your resume PDF file:", classes="field-label")
            yield Input(id="filepath-input", placeholder="C:\\path\\to\\resume.pdf")
            yield Label("Revision Name (optional - leave blank for auto-numbered):", classes="field-label")
            yield Input(id="name-input", placeholder="e.g., 'Software Engineer v2'")
            yield Label("Named revisions are kept permanently. Unnamed ones: only 5 most recent.", id="resume-info")
            with Horizontal(id="resume-buttons"):
                yield Button("Upload", id="upload", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    @on(Button.Pressed, "#upload")
    def upload_resume(self) -> None:
        """Upload the resume file."""
        import shutil
        import uuid

        filepath = self.query_one("#filepath-input", Input).value.strip()
        name = self.query_one("#name-input", Input).value.strip() or None

        if not filepath:
            return

        source_path = Path(filepath)
        if not source_path.exists():
            return

        session = get_session()
        try:
            profile = session.query(Profile).filter(Profile.id == self.profile_id).first()
            if not profile:
                return

            # Create resume directory
            resume_dir = get_resume_dir(self.profile_id)
            
            # Generate filename
            filename = f"resume_{uuid.uuid4().hex[:8]}.pdf"
            dest_path = resume_dir / filename
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            # Update profile
            profile.add_resume_version(filename, name)
            session.commit()
        finally:
            session.close()

        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(False)

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(False)


class ScrapeScreen(ModalScreen[bool]):
    """Modal screen for scraping jobs from a URL."""

    CSS = """
    ScrapeScreen {
        align: center middle;
    }

    #scrape-container {
        width: 80;
        height: 25;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    .field-label {
        margin-top: 1;
        color: $primary;
    }

    Input {
        margin-bottom: 0;
    }

    Select {
        margin-bottom: 1;
    }

    #scrape-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    #scrape-status {
        margin-top: 1;
        color: $warning;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="scrape-container"):
            yield Label("Scrape Jobs from URL", id="scrape-title")
            
            yield Label("Company Name:", classes="field-label")
            yield Input(id="company-input", placeholder="Company Name")
            
            yield Label("Job Board URL:", classes="field-label")
            yield Input(id="url-input", placeholder="https://company.com/careers or https://jobs.lever.co/company")
            
            yield Label("Scraper Type:", classes="field-label")
            yield Select(
                [
                    ("Lever Job Board", "lever"),
                    ("General Scraper", "general"),
                ],
                id="scraper-type",
                value="general",
            )
            
            yield Label("", id="scrape-status")
            
            with Horizontal(id="scrape-buttons"):
                yield Button("Scrape", id="scrape", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    def update_status(self, message: str) -> None:
        """Update status message."""
        self.query_one("#scrape-status", Label).update(message)

    @on(Button.Pressed, "#scrape")
    async def do_scrape(self) -> None:
        """Perform the scrape."""
        company = self.query_one("#company-input", Input).value.strip()
        url = self.query_one("#url-input", Input).value.strip()
        scraper_type = self.query_one("#scraper-type", Select).value

        if not company or not url:
            self.update_status("Please enter company name and URL")
            return

        self.update_status("Scraping... please wait...")
        
        try:
            if scraper_type == "lever":
                jobs = await self._scrape_lever(url, company)
            else:
                jobs = await self._scrape_general(url, company)
            
            # Save jobs to database
            session = get_session()
            try:
                added = 0
                for job_data in jobs:
                    existing = session.query(Job).filter(Job.apply_url == job_data["apply_url"]).first()
                    if existing:
                        continue
                    job = Job(
                        title=job_data["title"],
                        company=job_data["company"],
                        location=job_data.get("location"),
                        description=job_data.get("description"),
                        apply_url=job_data["apply_url"],
                        source_url=url,
                    )
                    if job_data.get("tags"):
                        job.set_tags(job_data["tags"])
                    session.add(job)
                    added += 1
                session.commit()
                self.update_status(f"Success! Added {added} new jobs.")
            finally:
                session.close()
        except Exception as e:
            self.update_status(f"Error: {str(e)[:50]}")

    async def _scrape_lever(self, url: str, company: str) -> list[dict]:
        """Scrape jobs from a Lever job board."""
        jobs = []
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            api_url = url.rstrip("/")
            if not api_url.endswith("/api"):
                api_url = api_url + "?mode=json"
            
            try:
                response = await client.get(api_url)
                response.raise_for_status()
                
                try:
                    data = response.json()
                    if isinstance(data, list):
                        for item in data:
                            jobs.append({
                                "title": item.get("text", "Unknown Title"),
                                "company": company,
                                "location": item.get("categories", {}).get("location", ""),
                                "description": item.get("descriptionPlain", ""),
                                "apply_url": item.get("hostedUrl", item.get("applyUrl", url)),
                                "tags": [],
                            })
                except:
                    return await self._scrape_general(url, company)
            except:
                return await self._scrape_general(url, company)
        
        return jobs

    async def _scrape_general(self, url: str, company: str) -> list[dict]:
        """Scrape jobs using general HTML parsing."""
        from urllib.parse import urljoin
        from bs4 import BeautifulSoup
        
        jobs = []
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            job_selectors = [
                "[class*='job-card']", "[class*='job-listing']", "[class*='posting']",
                "li[class*='job']", "article[class*='job']", "div[class*='job'][class*='item']",
                "a[href*='/jobs/']", "a[href*='/careers/']", "a[href*='/positions/']",
            ]
            
            seen_urls = set()
            for selector in job_selectors:
                for elem in soup.select(selector):
                    title_elem = elem.select_one("h2, h3, h4, [class*='title'], a")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue
                    
                    link = elem.get("href") if elem.name == "a" else None
                    if not link:
                        link_elem = elem.select_one("a[href]")
                        if link_elem:
                            link = link_elem.get("href")
                    
                    if not link:
                        continue
                    
                    if link.startswith("/"):
                        link = urljoin(url, link)
                    
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)
                    
                    location = None
                    loc_elem = elem.select_one("[class*='location']")
                    if loc_elem:
                        location = loc_elem.get_text(strip=True)
                    
                    jobs.append({
                        "title": title[:200],
                        "company": company,
                        "location": location,
                        "description": None,
                        "apply_url": link,
                        "tags": [],
                    })
            
        return jobs

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(False)

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(False)


class AddApplicationScreen(ModalScreen[bool]):
    """Modal screen for manually adding a job application."""

    CSS = """
    AddApplicationScreen {
        align: center middle;
    }

    #add-app-container {
        width: 70;
        height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    .field-label {
        margin-top: 1;
        color: $primary;
    }

    Input {
        margin-bottom: 0;
    }

    Select {
        margin-bottom: 1;
        width: 100%;
    }

    #add-app-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.profiles: list[Profile] = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        session = get_session()
        try:
            self.profiles = list(session.query(Profile).all())
        finally:
            session.close()

        profile_options = [(p.name, p.id) for p in self.profiles]
        if not profile_options:
            profile_options = [("No profiles", "")]

        with Vertical(id="add-app-container"):
            yield Label("Add Job Application", id="add-app-title")
            
            yield Label("Company:", classes="field-label")
            yield Input(id="company-input", placeholder="Company Name")
            
            yield Label("Job Title:", classes="field-label")
            yield Input(id="title-input", placeholder="Software Engineer")
            
            yield Label("Apply URL:", classes="field-label")
            yield Input(id="url-input", placeholder="https://company.com/apply")
            
            yield Label("Location:", classes="field-label")
            yield Input(id="location-input", placeholder="City, State")
            
            yield Label("Profile Applied With:", classes="field-label")
            yield Select(profile_options, id="profile-select", value=profile_options[0][1] if profile_options else "")
            
            with Horizontal(id="add-app-buttons"):
                yield Button("Add Application", id="add", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    @on(Button.Pressed, "#add")
    def add_application(self) -> None:
        """Add the application."""
        company = self.query_one("#company-input", Input).value.strip()
        title = self.query_one("#title-input", Input).value.strip()
        url = self.query_one("#url-input", Input).value.strip()
        location = self.query_one("#location-input", Input).value.strip()
        profile_id = self.query_one("#profile-select", Select).value

        if not company or not title or not url:
            return

        session = get_session()
        try:
            job = Job(
                title=title,
                company=company,
                location=location if location else None,
                apply_url=url,
                is_applied=True,
                applied_at=datetime.datetime.now(),
                profile_id=profile_id if profile_id else None,
            )
            session.add(job)
            session.commit()
        finally:
            session.close()

        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(False)

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(False)


class HiringCafeSearchScreen(ModalScreen[bool]):
    """Modal screen for searching hiring.cafe API."""

    CSS = """
    HiringCafeSearchScreen {
        align: center middle;
    }

    #search-container {
        width: 80;
        height: 25;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    .field-label {
        margin-top: 1;
        color: $primary;
    }

    Input {
        margin-bottom: 0;
    }

    #search-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    #search-status {
        margin-top: 1;
        color: $warning;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical(id="search-container"):
            yield Label("Search hiring.cafe Jobs", id="search-title")
            
            yield Label("Job Title / Keywords:", classes="field-label")
            yield Input(id="query-input", placeholder="Software Engineer, Data Scientist, etc.")
            
            yield Label("Location (optional):", classes="field-label")
            yield Input(id="location-input", placeholder="San Francisco, Remote, etc.")
            
            yield Label("Max days since posted (default 90):", classes="field-label")
            yield Input(id="days-input", placeholder="90", value="90")
            
            yield Label("", id="search-status")
            
            with Horizontal(id="search-buttons"):
                yield Button("Search & Import", id="search", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    def update_status(self, message: str) -> None:
        """Update status message."""
        self.query_one("#search-status", Label).update(message)

    @on(Button.Pressed, "#search")
    async def do_search(self) -> None:
        """Perform the search."""
        query = self.query_one("#query-input", Input).value.strip()
        location = self.query_one("#location-input", Input).value.strip()
        days_str = self.query_one("#days-input", Input).value.strip()
        
        try:
            max_days = int(days_str) if days_str else 90
        except ValueError:
            max_days = 90

        if not query:
            self.update_status("Please enter search keywords")
            return

        self.update_status("Searching hiring.cafe... please wait...")
        
        try:
            jobs = await self._search_hiring_cafe(query, location, max_days)
            
            session = get_session()
            try:
                added = 0
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=max_days)
                
                for job_data in jobs:
                    posted_at = job_data.get("posted_at")
                    if posted_at and posted_at < cutoff_date:
                        continue
                    
                    existing = session.query(Job).filter(Job.apply_url == job_data["apply_url"]).first()
                    if existing:
                        continue
                    
                    job = Job(
                        title=job_data["title"],
                        company=job_data["company"],
                        location=job_data.get("location"),
                        description=job_data.get("description"),
                        apply_url=job_data["apply_url"],
                        source_url="hiring.cafe",
                    )
                    if job_data.get("tags"):
                        job.set_tags(job_data["tags"])
                    session.add(job)
                    added += 1
                session.commit()
                self.update_status(f"Success! Added {added} new jobs.")
            finally:
                session.close()
        except Exception as e:
            self.update_status(f"Error: {str(e)[:50]}")

    async def _search_hiring_cafe(self, query: str, location: str, max_days: int) -> list[dict]:
        """Search hiring.cafe API for jobs."""
        from bs4 import BeautifulSoup
        jobs = []
        
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            params = {"q": query, "limit": 100}
            if location:
                params["location"] = location
            
            try:
                response = await client.get("https://hiring.cafe/api/jobs", params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("jobs", data.get("results", data if isinstance(data, list) else []))
                    
                    for item in items:
                        posted_at = None
                        date_str = item.get("posted_at") or item.get("postedAt") or item.get("date")
                        if date_str:
                            try:
                                posted_at = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            except:
                                pass
                        
                        jobs.append({
                            "title": item.get("title", item.get("job_title", "Unknown")),
                            "company": item.get("company", item.get("company_name", "Unknown")),
                            "location": item.get("location", ""),
                            "description": item.get("description", ""),
                            "apply_url": item.get("url", item.get("apply_url", item.get("link", ""))),
                            "posted_at": posted_at,
                            "tags": item.get("tags", []),
                        })
                else:
                    response = await client.get(f"https://hiring.cafe/jobs?q={query}")
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                        
                        for card in soup.select("[class*='job'], article, .posting"):
                            title_elem = card.select_one("h2, h3, [class*='title']")
                            company_elem = card.select_one("[class*='company']")
                            link_elem = card.select_one("a[href]")
                            
                            if title_elem and link_elem:
                                jobs.append({
                                    "title": title_elem.get_text(strip=True),
                                    "company": company_elem.get_text(strip=True) if company_elem else "Unknown",
                                    "location": "",
                                    "description": "",
                                    "apply_url": link_elem.get("href", ""),
                                    "posted_at": None,
                                    "tags": [],
                                })
            except Exception as e:
                raise Exception(f"Failed to fetch from hiring.cafe: {e}")
        
        return jobs

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(False)

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(False)


# ============================================================================
# Main Application
# ============================================================================


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

    TabbedContent {
        height: 100%;
    }

    TabPane {
        padding: 0;
    }

    .tab-content {
        height: 100%;
    }

    #profile-view {
        padding: 1;
    }

    #profile-info {
        height: auto;
        margin-bottom: 1;
    }

    #profile-actions {
        height: 3;
        margin-bottom: 1;
    }

    #profile-actions Button {
        margin-right: 1;
    }

    #history-actions {
        height: 3;
        margin-bottom: 1;
        padding: 0 1;
    }

    #history-actions Button {
        margin-right: 1;
    }

    #resume-list {
        height: 1fr;
        border: solid $primary;
    }

    .profile-field {
        margin-bottom: 0;
    }

    .profile-value {
        color: $text;
        margin-left: 2;
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
        Binding("slash", "search", "Search"),
        Binding("s", "scrape", "Scrape Jobs"),
        Binding("h", "hiring_cafe", "hiring.cafe"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("1", "switch_tab_jobs", "Jobs Tab", show=False),
        Binding("2", "switch_tab_history", "History Tab", show=False),
        Binding("3", "switch_tab_profiles", "Profiles Tab", show=False),
    ]

    def __init__(self) -> None:
        """Initialize the app."""
        super().__init__()
        self.jobs: list[dict] = []
        self.applied_jobs: list[dict] = []
        self.current_filter = "all"
        self.search_term = ""
        self.selected_profile_id: Optional[str] = None
        self.selected_profile: Optional[Profile] = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("Jobs", id="jobs-tab"):
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
            with TabPane("Application History", id="history-tab"):
                with Vertical(classes="tab-content"):
                    with Horizontal(id="history-actions"):
                        yield Button("Add Application", id="add-application-btn", variant="success")
                        yield Button("Remove Selected", id="remove-application-btn", variant="error")
                    yield DataTable(id="history-table")
            with TabPane("Profiles", id="profiles-tab"):
                with Vertical(id="profile-view"):
                    with Horizontal(id="profile-actions"):
                        yield Button("New Profile", id="new-profile-btn", variant="success")
                        yield Button("Edit Profile", id="edit-profile-btn", variant="primary")
                        yield Button("Delete Profile", id="delete-profile-btn", variant="error")
                        yield Button("Upload Resume", id="upload-resume-btn", variant="primary")
                    yield OptionList(id="profile-list")
                    yield Static(id="profile-details")
        yield Static("Ready | Press ? for help", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        init_db()
        
        table = self.query_one("#job-table", DataTable)
        table.add_columns("Company", "Title", "Location", "Tags", "Status")
        table.cursor_type = "row"
        
        history_table = self.query_one("#history-table", DataTable)
        history_table.add_columns("Company", "Title", "Applied Date", "Profile")
        history_table.cursor_type = "row"
        
        self.refresh_jobs()
        self.refresh_history()
        self.refresh_profiles()

    def refresh_jobs(self) -> None:
        """Refresh job list from database."""
        session = get_session()
        try:
            query = session.query(Job)

            new_grad_filter = self.query_one("#new-grad-filter", Switch).value
            applied_filter = self.query_one("#applied-filter", Switch).value
            pending_filter = self.query_one("#pending-filter", Switch).value
            search_input = self.query_one("#search-input", Input).value

            if not applied_filter:
                query = query.filter(Job.is_applied.is_(False))

            if new_grad_filter:
                query = query.filter(Job.tags.contains('"new-grad"'))
            if applied_filter:
                query = query.filter(Job.is_applied.is_(True))
            if pending_filter:
                query = query.filter(Job.is_pending.is_(True))
            if search_input:
                term = f"%{search_input}%"
                query = query.filter(
                    (Job.title.ilike(term))
                    | (Job.company.ilike(term))
                    | (Job.description.ilike(term))
                )
            
            cutoff = datetime.datetime.now() - datetime.timedelta(days=90)
            query = query.filter(Job.scraped_at >= cutoff)

            jobs = query.order_by(Job.scraped_at.desc()).limit(500).all()
            self.jobs = [job.to_dict() for job in jobs]

            table = self.query_one("#job-table", DataTable)
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

    def refresh_history(self) -> None:
        """Refresh application history."""
        session = get_session()
        try:
            jobs = session.query(Job).filter(Job.is_applied.is_(True)).order_by(Job.applied_at.desc()).all()
            self.applied_jobs = [job.to_dict() for job in jobs]

            table = self.query_one("#history-table", DataTable)
            table.clear()
            for job in self.applied_jobs:
                profile_name = "N/A"
                if job.get("profile_id"):
                    profile = session.query(Profile).filter(Profile.id == job["profile_id"]).first()
                    if profile:
                        profile_name = profile.name

                applied_date = ""
                if job.get("applied_at"):
                    try:
                        dt = datetime.datetime.fromisoformat(job["applied_at"])
                        applied_date = dt.strftime("%Y-%m-%d")
                    except:
                        pass

                table.add_row(
                    job["company"][:25],
                    job["title"][:35],
                    applied_date,
                    profile_name[:15],
                    key=job["id"],
                )
        finally:
            session.close()

    def refresh_profiles(self) -> None:
        """Refresh profile list."""
        session = get_session()
        try:
            profiles = session.query(Profile).all()
            profile_list = self.query_one("#profile-list", OptionList)
            profile_list.clear_options()
            
            for profile in profiles:
                resume_count = len(profile.get_resume_versions())
                profile_list.add_option(Option(
                    f"{profile.name} ({profile.email}) - {resume_count} resumes",
                    id=profile.id,
                ))
            
            if profiles and not self.selected_profile_id:
                self.selected_profile_id = profiles[0].id
                self._update_profile_details()
        finally:
            session.close()

    def _update_profile_details(self) -> None:
        """Update the profile details display."""
        if not self.selected_profile_id:
            self.query_one("#profile-details", Static).update("No profile selected")
            return

        session = get_session()
        try:
            profile = session.query(Profile).filter(Profile.id == self.selected_profile_id).first()
            if not profile:
                self.query_one("#profile-details", Static).update("Profile not found")
                return

            self.selected_profile = profile
            
            details = []
            details.append(f"[bold]Name:[/bold] {profile.name}")
            details.append(f"[bold]Email:[/bold] {profile.email}")
            if profile.phone:
                details.append(f"[bold]Phone:[/bold] {profile.phone}")
            
            address = profile.get_full_address()
            if address:
                details.append(f"[bold]Address:[/bold] {address}")
            
            if profile.linkedin_url:
                details.append(f"[bold]LinkedIn:[/bold] {profile.linkedin_url}")
            if profile.github_url:
                details.append(f"[bold]GitHub:[/bold] {profile.github_url}")
            if profile.portfolio_url:
                details.append(f"[bold]Portfolio:[/bold] {profile.portfolio_url}")
            
            details.append("")
            details.append("[bold]Resume Versions:[/bold]")
            versions = profile.get_resume_versions()
            if versions:
                for v in versions[-5:]:
                    named = " (Named)" if v.get("is_named") else ""
                    details.append(f"  • {v.get('name', 'Unnamed')}{named} - {v.get('uploaded_at', 'Unknown')[:10]}")
            else:
                details.append("  No resumes uploaded")
            
            self.query_one("#profile-details", Static).update("\n".join(details))
        finally:
            session.close()

    @on(OptionList.OptionSelected, "#profile-list")
    def profile_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle profile selection."""
        if event.option.id:
            self.selected_profile_id = str(event.option.id)
            self._update_profile_details()

    def update_status(self, message: str) -> None:
        """Update status bar message."""
        status = self.query_one("#status-bar", Static)
        status.update(message)

    def get_selected_job(self) -> Optional[dict]:
        """Get the currently selected job from jobs tab."""
        table = self.query_one("#job-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.jobs):
            return self.jobs[table.cursor_row]
        return None

    def get_selected_applied_job(self) -> Optional[dict]:
        """Get the currently selected job from history tab."""
        table = self.query_one("#history-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.applied_jobs):
            return self.applied_jobs[table.cursor_row]
        return None

    @on(Switch.Changed)
    def filter_changed(self) -> None:
        """Handle filter switch changes."""
        self.refresh_jobs()

    @on(Input.Submitted, "#search-input")
    def search_submitted(self) -> None:
        """Handle search input submission."""
        self.refresh_jobs()

    @on(Button.Pressed, "#add-application-btn")
    async def add_application_pressed(self) -> None:
        """Handle add application button."""
        result = await self.push_screen_wait(AddApplicationScreen())
        if result:
            self.refresh_history()
            self.update_status("Application added")

    @on(Button.Pressed, "#remove-application-btn")
    def remove_application_pressed(self) -> None:
        """Handle remove application button."""
        job = self.get_selected_applied_job()
        if not job:
            self.update_status("No application selected")
            return
        
        session = get_session()
        try:
            db_job = session.query(Job).filter(Job.id == job["id"]).first()
            if db_job:
                db_job.is_applied = False
                db_job.applied_at = None
                db_job.profile_id = None
                session.commit()
                self.refresh_history()
                self.refresh_jobs()
                self.update_status(f"Removed application: {job['title']}")
        finally:
            session.close()

    @on(Button.Pressed, "#new-profile-btn")
    async def new_profile_pressed(self) -> None:
        """Handle new profile button."""
        result = await self.push_screen_wait(ProfileEditScreen())
        if result:
            self.refresh_profiles()
            self.update_status("Profile created")

    @on(Button.Pressed, "#edit-profile-btn")
    async def edit_profile_pressed(self) -> None:
        """Handle edit profile button."""
        if not self.selected_profile_id:
            self.update_status("No profile selected")
            return
        result = await self.push_screen_wait(ProfileEditScreen(self.selected_profile_id))
        if result:
            self.refresh_profiles()
            self._update_profile_details()
            self.update_status("Profile updated")

    @on(Button.Pressed, "#delete-profile-btn")
    def delete_profile_pressed(self) -> None:
        """Handle delete profile button."""
        if not self.selected_profile_id:
            self.update_status("No profile selected")
            return
        
        session = get_session()
        try:
            profile = session.query(Profile).filter(Profile.id == self.selected_profile_id).first()
            if profile:
                session.delete(profile)
                session.commit()
                self.selected_profile_id = None
                self.refresh_profiles()
                self.update_status("Profile deleted")
        finally:
            session.close()

    @on(Button.Pressed, "#upload-resume-btn")
    async def upload_resume_pressed(self) -> None:
        """Handle upload resume button."""
        if not self.selected_profile_id:
            self.update_status("No profile selected")
            return
        result = await self.push_screen_wait(ResumeUploadScreen(self.selected_profile_id))
        if result:
            self.refresh_profiles()
            self._update_profile_details()
            self.update_status("Resume uploaded")

    def action_refresh(self) -> None:
        """Refresh all data."""
        self.refresh_jobs()
        self.refresh_history()
        self.refresh_profiles()

    def action_cursor_down(self) -> None:
        """Move cursor down (vim j key)."""
        try:
            focused = self.focused
            if isinstance(focused, DataTable):
                focused.action_cursor_down()
        except:
            pass

    def action_cursor_up(self) -> None:
        """Move cursor up (vim k key)."""
        try:
            focused = self.focused
            if isinstance(focused, DataTable):
                focused.action_cursor_up()
        except:
            pass

    def action_switch_tab_jobs(self) -> None:
        """Switch to jobs tab."""
        self.query_one(TabbedContent).active = "jobs-tab"

    def action_switch_tab_history(self) -> None:
        """Switch to history tab."""
        self.query_one(TabbedContent).active = "history-tab"

    def action_switch_tab_profiles(self) -> None:
        """Switch to profiles tab."""
        self.query_one(TabbedContent).active = "profiles-tab"

    def action_open_job(self) -> None:
        """Open job link in browser and mark as pending."""
        job = self.get_selected_job()
        if not job:
            self.update_status("No job selected")
            return

        url = job.get("apply_url")
        if url:
            session = get_session()
            try:
                db_job = session.query(Job).filter(Job.id == job["id"]).first()
                if db_job:
                    db_job.is_pending = True
                    session.commit()
            finally:
                session.close()

            webbrowser.open(url)
            self.update_status(f"Opened: {job['title']} - Press 'a' to mark as applied")
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
        self.refresh_history()

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
        result = await self.push_screen_wait(ProfileEditScreen())
        if result:
            self.refresh_profiles()
            self.update_status("Profile added")

    async def action_scrape(self) -> None:
        """Open scrape modal."""
        result = await self.push_screen_wait(ScrapeScreen())
        if result:
            self.refresh_jobs()

    async def action_hiring_cafe(self) -> None:
        """Open hiring.cafe search modal."""
        result = await self.push_screen_wait(HiringCafeSearchScreen())
        if result:
            self.refresh_jobs()

    def action_toggle_filter(self) -> None:
        """Toggle between filter presets."""
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
