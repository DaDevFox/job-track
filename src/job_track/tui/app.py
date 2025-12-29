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
    ProgressBar,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from job_track.db.models import Job, Profile, AppSettings, ScraperSource, get_resume_dir, get_session, init_db
from job_track.scraper.simplify_jobs import SimplifyJobsScraper, SimplifyJobsConfig
from job_track.scraper.hiring_cafe import HiringCafeScraper, SearchConfig, PLAYWRIGHT_AVAILABLE
from job_track.scraper.scraper import ScrapeJobEvent, ScrapeProgressEvent, ScrapeCompleteEvent, ScrapeErrorEvent


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
                                f"{profile.profile_name} ({profile.get_full_name()}){resume_info}",
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
                # Profile Info
                yield Label("── Profile ──", classes="section-header")
                yield Label("Profile Name:", classes="field-label")
                yield Input(
                    id="profile-name-input",
                    placeholder="e.g., Tech Resume, Finance Applications",
                    value=self.profile.profile_name if self.profile else "",
                )
                
                # Basic Info
                yield Label("── Personal Information ──", classes="section-header")
                yield Label("First Name:", classes="field-label")
                yield Input(
                    id="first-name-input",
                    placeholder="First Name",
                    value=self.profile.first_name if self.profile else "",
                )
                yield Label("Last Name:", classes="field-label")
                yield Input(
                    id="last-name-input",
                    placeholder="Last Name",
                    value=self.profile.last_name if self.profile else "",
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
        profile_name = self.query_one("#profile-name-input", Input).value.strip()
        first_name = self.query_one("#first-name-input", Input).value.strip()
        last_name = self.query_one("#last-name-input", Input).value.strip()
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

        if not profile_name or not first_name or not last_name or not email:
            return  # Basic validation

        session = get_session()
        try:
            if self.profile_id:
                profile = session.query(Profile).filter(Profile.id == self.profile_id).first()
                if profile:
                    profile.profile_name = profile_name
                    profile.first_name = first_name
                    profile.last_name = last_name
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
                    profile_name=profile_name,
                    first_name=first_name,
                    last_name=last_name,
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

        profile_options = [(p.profile_name, p.id) for p in self.profiles]
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


class ScrapingSourcesScreen(ModalScreen[bool]):
    """Modal screen for selecting and triggering scraping sources with progress tracking."""

    CSS = """
    ScrapingSourcesScreen {
        align: center middle;
    }

    #sources-container {
        width: 90;
        height: 40;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #sources-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #source-select {
        width: 100%;
        margin-bottom: 1;
    }

    #source-info {
        height: 6;
        border: solid $secondary;
        padding: 1;
        margin-bottom: 1;
    }

    #progress-section {
        height: 10;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    #progress-bar {
        width: 100%;
        height: 1;
        margin: 1 0;
    }

    #progress-status {
        height: 2;
    }

    #job-log {
        height: 4;
        overflow-y: auto;
        color: $text-muted;
    }

    #sources-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.sources: list[ScraperSource] = []
        self.selected_source: Optional[ScraperSource] = None
        self.api_url = "http://localhost:8787"
        self.is_scraping = False
        self.jobs_found = 0
        self.jobs_added = 0

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        from textual.widgets import ProgressBar
        
        session = get_session()
        try:
            self.sources = list(session.query(ScraperSource).filter(ScraperSource.enabled.is_(True)).all())
            settings = AppSettings.get_settings(session)
            self.api_url = settings.api_server_url
        finally:
            session.close()

        source_options = [(s.name, s.id) for s in self.sources]
        if not source_options:
            source_options = [("No sources configured", "")]

        with Vertical(id="sources-container"):
            yield Label("Scrape Jobs from Source", id="sources-title")
            
            yield Label("Select Scraping Source:")
            yield Select(source_options, id="source-select", value=source_options[0][1] if source_options else "")
            
            yield Static("Select a source to see details", id="source-info")
            
            # Progress section
            with Container(id="progress-section"):
                yield Label("Progress:", classes="field-label")
                yield ProgressBar(id="progress-bar", total=100, show_eta=False)
                yield Static("Ready to scrape", id="progress-status")
                yield Static("", id="job-log")
            
            with Horizontal(id="sources-buttons"):
                yield Button("Scrape Now", id="scrape-now", variant="success")
                yield Button("Scrape via API (Streaming)", id="scrape-api-stream", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def on_mount(self) -> None:
        """Called when mounted."""
        if self.sources:
            self._update_source_info(self.sources[0].id)

    def _update_source_info(self, source_id: str) -> None:
        """Update the source info display."""
        for source in self.sources:
            if source.id == source_id:
                self.selected_source = source
                config = source.get_config()
                info_lines = [
                    f"[bold]Type:[/bold] {ScraperSource.SOURCE_TYPES.get(source.source_type, source.source_type)}",
                    f"[bold]Schedule:[/bold] {source.schedule}",
                    f"[bold]Last Scraped:[/bold] {source.last_scraped_at.strftime('%Y-%m-%d %H:%M') if source.last_scraped_at else 'Never'}",
                ]
                if config:
                    config_str = ", ".join(f"{k}: {v}" for k, v in list(config.items())[:3])
                    info_lines.append(f"[bold]Config:[/bold] {config_str[:60]}...")
                self.query_one("#source-info", Static).update("\n".join(info_lines))
                return

    @on(Select.Changed, "#source-select")
    def source_changed(self, event: Select.Changed) -> None:
        """Handle source selection change."""
        if event.value:
            self._update_source_info(str(event.value))

    def update_progress(self, progress: float, status: str) -> None:
        """Update progress bar and status."""
        from textual.widgets import ProgressBar
        self.query_one("#progress-bar", ProgressBar).update(progress=progress)
        self.query_one("#progress-status", Static).update(status)

    def update_job_log(self, message: str) -> None:
        """Update the job log with recent activity."""
        self.query_one("#job-log", Static).update(message)

    @on(Button.Pressed, "#scrape-now")
    async def scrape_now(self) -> None:
        """Perform scraping locally using streaming scrapers with real-time progress."""
        if not self.selected_source or self.is_scraping:
            return

        self.is_scraping = True
        self.jobs_found = 0
        self.jobs_added = 0
        all_jobs = []
        last_job_info = ""
        
        try:
            config = self.selected_source.get_config()
            source_type = self.selected_source.source_type
            
            # Create the appropriate streaming scraper
            scraper = None
            if source_type == "simplify_jobs":
                scraper_config = SimplifyJobsConfig(
                    include_inactive=config.get("include_inactive", False),
                    categories=config.get("categories", ["software-engineering"]),
                    max_age_days=config.get("max_age_days"),
                )
                scraper = SimplifyJobsScraper(scraper_config)
            elif source_type == "hiring_cafe":
                if not PLAYWRIGHT_AVAILABLE:
                    self.update_progress(0, "✗ Playwright not installed for hiring.cafe")
                    return
                experience_levels = config.get("experience_levels", ["entry-level", "internship"])
                if isinstance(experience_levels, str):
                    experience_levels = [e.strip() for e in experience_levels.split(",")]
                scraper_config = SearchConfig(
                    query=config.get("query", "software engineer"),
                    department=config.get("department", "software-engineering"),
                    experience_levels=experience_levels,
                    location=config.get("location", "United States"),
                    max_results=config.get("max_results", 50),
                )
                scraper = HiringCafeScraper(scraper_config)
            else:
                # Fall back to the old method for custom URLs
                jobs = await self._run_scraper_with_progress(self.selected_source)
                self.update_progress(80, f"Saving {len(jobs)} jobs to database...")
                added = await self._save_jobs(jobs)
                self.update_progress(100, f"✓ Complete! Found {len(jobs)}, added {added} new jobs.")
                return
            
            # Use the streaming scraper
            async for event in scraper.scrape_stream():
                if isinstance(event, ScrapeProgressEvent):
                    # Use percentage-based progress directly
                    step = event.step
                    total = event.total_steps
                    if total == 100:
                        progress = step
                    else:
                        progress = int((step / total) * 100)
                    self.update_progress(progress, event.message)
                    if event.jobs_found > 0:
                        self.jobs_found = event.jobs_found
                
                elif isinstance(event, ScrapeJobEvent):
                    job = event.job
                    all_jobs.append({
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "description": job.description or "",
                        "apply_url": job.apply_url,
                        "tags": job.tags,
                        "source": source_type,
                    })
                    self.jobs_found = len(all_jobs)
                    last_job_info = f"{job.title} @ {job.company}"
                    if len(all_jobs) % 5 == 0:
                        self.update_job_log(f"Found {len(all_jobs)} jobs... {last_job_info[:40]}")
                
                elif isinstance(event, ScrapeCompleteEvent):
                    self.update_progress(90, f"Saving {len(all_jobs)} jobs to database...")
                    added = await self._save_jobs(all_jobs)
                    self.jobs_added = added
                    
                    # Update last scraped time
                    session = get_session()
                    try:
                        source = session.query(ScraperSource).filter(ScraperSource.id == self.selected_source.id).first()
                        if source:
                            source.last_scraped_at = datetime.datetime.now()
                            session.commit()
                    finally:
                        session.close()
                    
                    self.update_progress(100, f"✓ Complete! Found {len(all_jobs)}, added {added} new jobs.")
                    self.update_job_log(f"Last job: {last_job_info[:50]}")
                
                elif isinstance(event, ScrapeErrorEvent):
                    self.update_progress(0, f"✗ Error: {event.message[:60]}")
            
        except Exception as e:
            self.update_progress(0, f"✗ Error: {str(e)[:60]}")
        finally:
            self.is_scraping = False

    @on(Button.Pressed, "#scrape-api-stream")
    async def scrape_via_api_stream(self) -> None:
        """Trigger scraping via the API server with SSE streaming progress."""
        if not self.selected_source or self.is_scraping:
            return

        self.is_scraping = True
        self.jobs_found = 0
        self.jobs_added = 0
        
        self.update_progress(5, f"Connecting to API at {self.api_url}...")
        
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                # Use the streaming endpoint
                url = f"{self.api_url}/api/scrape/stream/{self.selected_source.id}"
                
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        self.update_progress(0, f"API error: {response.status_code}")
                        return
                    
                    last_job = ""
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        if line.startswith("event: "):
                            event_type = line[7:]
                        elif line.startswith("data: "):
                            try:
                                import json
                                data = json.loads(line[6:])
                                
                                if event_type == "start":
                                    self.update_progress(10, f"Started scraping {data.get('source_name', '')}...")
                                
                                elif event_type == "progress":
                                    step = data.get("step", 0)
                                    total = data.get("total_steps", 100)
                                    # Handle both percentage-based (total=100) and step-based progress
                                    if total == 100:
                                        progress = step
                                    else:
                                        progress = int((step / total) * 100)
                                    self.update_progress(progress, data.get("message", "Processing..."))
                                    self.jobs_found = data.get("jobs_found", self.jobs_found)
                                
                                elif event_type == "job":
                                    self.jobs_found += 1
                                    last_job = f"{data.get('title', '')} @ {data.get('company', '')}"
                                    if self.jobs_found % 5 == 0:  # Update every 5 jobs to avoid flickering
                                        self.update_job_log(f"Found {self.jobs_found} jobs... {last_job[:40]}")
                                
                                elif event_type == "complete":
                                    self.jobs_found = data.get("total_scraped", 0)
                                    self.jobs_added = data.get("total_added", 0)
                                    self.update_progress(100, 
                                        f"✓ Complete! Found {self.jobs_found}, added {self.jobs_added} new jobs.")
                                    self.update_job_log(f"Last: {last_job[:50]}")
                                
                                elif event_type == "error":
                                    self.update_progress(0, f"✗ Error: {data.get('message', 'Unknown error')}")
                            
                            except json.JSONDecodeError:
                                pass
        
        except httpx.ConnectError:
            self.update_progress(0, f"✗ Cannot connect to API at {self.api_url}")
        except Exception as e:
            self.update_progress(0, f"✗ Error: {str(e)[:60]}")
        finally:
            self.is_scraping = False

    async def _run_scraper_with_progress(self, source: ScraperSource) -> list[dict]:
        """Run the appropriate scraper based on source type with progress updates."""
        config = source.get_config()
        
        if source.source_type == "hiring_cafe":
            self.update_progress(20, "Searching hiring.cafe...")
            return await self._scrape_hiring_cafe_source(config)
        elif source.source_type == "simplify_jobs":
            self.update_progress(20, "Fetching SimplifyJobs GitHub...")
            return await self._scrape_simplify_jobs_source(config)
        elif source.source_type == "custom_url":
            self.update_progress(20, "Scraping custom URLs...")
            return await self._scrape_custom_urls(config)
        else:
            raise ValueError(f"Unknown source type: {source.source_type}")

    async def _scrape_hiring_cafe_source(self, config: dict) -> list[dict]:
        """Scrape from hiring.cafe with given config."""
        from bs4 import BeautifulSoup
        jobs = []
        
        query = config.get("query", "software engineer")
        location = config.get("location", "")
        
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            params = {"q": query, "limit": config.get("max_results", 50)}
            if location:
                params["location"] = location
            
            try:
                response = await client.get("https://hiring.cafe/api/jobs", params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("jobs", data.get("results", data if isinstance(data, list) else []))
                    
                    for item in items:
                        jobs.append({
                            "title": item.get("title", item.get("job_title", "Unknown")),
                            "company": item.get("company", item.get("company_name", "Unknown")),
                            "location": item.get("location", ""),
                            "description": item.get("description", ""),
                            "apply_url": item.get("url", item.get("apply_url", item.get("link", ""))),
                            "tags": item.get("tags", []),
                            "source": "hiring.cafe",
                        })
            except Exception:
                pass
        
        return jobs

    async def _scrape_simplify_jobs_source(self, config: dict) -> list[dict]:
        """Scrape from SimplifyJobs GitHub."""
        jobs = []
        
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                response = await client.get(
                    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
                )
                if response.status_code == 200:
                    content = response.text
                    # Parse the markdown table
                    import re
                    # Find table rows (lines starting with |)
                    lines = content.split('\n')
                    in_table = False
                    for line in lines:
                        if '| Company |' in line or '| --- |' in line:
                            in_table = True
                            continue
                        if in_table and line.startswith('|'):
                            parts = [p.strip() for p in line.split('|')[1:-1]]
                            if len(parts) >= 4:
                                company = re.sub(r'\[([^\]]+)\].*', r'\1', parts[0]).strip()
                                title = parts[1].strip() if len(parts) > 1 else "Software Engineer"
                                location = parts[2].strip() if len(parts) > 2 else ""
                                
                                # Extract URL from markdown link
                                url_match = re.search(r'\[.*?\]\((.*?)\)', parts[-1] if parts[-1] else parts[0])
                                apply_url = url_match.group(1) if url_match else ""
                                
                                if company and apply_url and "🔒" not in line:
                                    jobs.append({
                                        "title": title or "Software Engineer",
                                        "company": company,
                                        "location": location,
                                        "description": "",
                                        "apply_url": apply_url,
                                        "tags": ["new-grad"],
                                        "source": "simplify_jobs",
                                    })
            except Exception:
                pass
        
        return jobs

    async def _scrape_custom_urls(self, config: dict) -> list[dict]:
        """Scrape from custom URLs."""
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        jobs = []
        urls = config.get("urls", [])
        company = config.get("company", "Unknown")
        
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                        
                        job_selectors = [
                            "[class*='job-card']", "[class*='job-listing']",
                            "a[href*='/jobs/']", "a[href*='/careers/']",
                        ]
                        
                        seen_urls = set()
                        for selector in job_selectors:
                            for elem in soup.select(selector)[:20]:
                                title_elem = elem.select_one("h2, h3, h4, [class*='title'], a")
                                if not title_elem:
                                    continue
                                title = title_elem.get_text(strip=True)
                                if not title:
                                    continue
                                
                                link = elem.get("href") if elem.name == "a" else None
                                if not link:
                                    link_elem = elem.select_one("a[href]")
                                    if link_elem:
                                        link = link_elem.get("href")
                                
                                if not link or link in seen_urls:
                                    continue
                                
                                if link.startswith("/"):
                                    link = urljoin(url, link)
                                
                                seen_urls.add(link)
                                jobs.append({
                                    "title": title[:200],
                                    "company": company,
                                    "location": None,
                                    "description": None,
                                    "apply_url": link,
                                    "tags": [],
                                    "source": "custom",
                                })
                except Exception:
                    pass
        
        return jobs

    async def _save_jobs(self, jobs: list[dict]) -> int:
        """Save scraped jobs to database, return count of newly added."""
        session = get_session()
        added = 0
        try:
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
                    source_url=job_data.get("source", ""),
                )
                if job_data.get("tags"):
                    job.set_tags(job_data["tags"])
                session.add(job)
                added += 1
            session.commit()
        finally:
            session.close()
        
        return added

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel and close."""
        self.dismiss(False)

    def key_escape(self) -> None:
        """Handle escape key."""
        self.dismiss(False)


class SettingsScreen(ModalScreen[bool]):
    """Modal screen for application settings."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 85;
        height: 40;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #settings-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .section-header {
        margin-top: 1;
        text-style: bold;
        color: $secondary;
    }

    .field-label {
        margin-top: 1;
        color: $primary;
    }

    #settings-scroll {
        height: 1fr;
    }

    #sources-list {
        height: 12;
        border: solid $secondary;
        margin: 1 0;
    }

    #settings-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.settings: Optional[AppSettings] = None
        self.sources: list[ScraperSource] = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        session = get_session()
        try:
            self.settings = AppSettings.get_settings(session)
            self.sources = list(session.query(ScraperSource).all())
        finally:
            session.close()

        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")
            
            with VerticalScroll(id="settings-scroll"):
                # API Server Settings
                yield Label("── API Server ──", classes="section-header")
                yield Label("API Server URL (for remote scraping):", classes="field-label")
                yield Input(
                    id="api-url-input",
                    placeholder="http://localhost:8787",
                    value=self.settings.api_server_url if self.settings else "http://localhost:8787",
                )
                
                yield Label("Enable Auto-Scraping:", classes="field-label")
                with Horizontal():
                    yield Switch(id="auto-scrape-switch", value=self.settings.auto_scrape_enabled if self.settings else False)
                    yield Label("Automatically scrape on schedule")
                
                # Scraping Sources
                yield Label("── Scraping Sources ──", classes="section-header")
                yield Label("Configure source schedules (manual, hourly, daily, weekly):")
                yield OptionList(id="sources-list")
                
                with Horizontal():
                    yield Button("Add Source", id="add-source", variant="success")
                    yield Button("Edit Selected", id="edit-source", variant="primary")
                    yield Button("Delete Selected", id="delete-source", variant="error")
            
            with Horizontal(id="settings-buttons"):
                yield Button("Save", id="save", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    def on_mount(self) -> None:
        """Called when mounted."""
        self._refresh_sources_list()

    def _refresh_sources_list(self) -> None:
        """Refresh the sources list display."""
        session = get_session()
        try:
            self.sources = list(session.query(ScraperSource).all())
        finally:
            session.close()
        
        sources_list = self.query_one("#sources-list", OptionList)
        sources_list.clear_options()
        
        for source in self.sources:
            status = "✓" if source.enabled else "✗"
            schedule_icon = {"manual": "🖐️", "hourly": "⏰", "daily": "📅", "weekly": "📆"}.get(source.schedule, "❓")
            sources_list.add_option(Option(
                f"{status} {schedule_icon} {source.name} ({source.source_type})",
                id=source.id,
            ))

    @on(Button.Pressed, "#add-source")
    def add_source(self) -> None:
        """Add a new scraping source."""
        def on_result(result: bool) -> None:
            if result:
                self._refresh_sources_list()
        self.app.push_screen(EditSourceScreen(), on_result)

    @on(Button.Pressed, "#edit-source")
    def edit_source(self) -> None:
        """Edit the selected scraping source."""
        sources_list = self.query_one("#sources-list", OptionList)
        if sources_list.highlighted is not None and sources_list.highlighted < len(self.sources):
            source = self.sources[sources_list.highlighted]
            def on_result(result: bool) -> None:
                if result:
                    self._refresh_sources_list()
            self.app.push_screen(EditSourceScreen(source.id), on_result)

    @on(Button.Pressed, "#delete-source")
    def delete_source(self) -> None:
        """Delete the selected scraping source."""
        sources_list = self.query_one("#sources-list", OptionList)
        if sources_list.highlighted is not None and sources_list.highlighted < len(self.sources):
            source = self.sources[sources_list.highlighted]
            session = get_session()
            try:
                db_source = session.query(ScraperSource).filter(ScraperSource.id == source.id).first()
                if db_source:
                    session.delete(db_source)
                    session.commit()
            finally:
                session.close()
            self._refresh_sources_list()

    @on(Button.Pressed, "#save")
    def save_settings(self) -> None:
        """Save the settings."""
        api_url = self.query_one("#api-url-input", Input).value.strip()
        auto_scrape = self.query_one("#auto-scrape-switch", Switch).value

        if not api_url:
            api_url = "http://localhost:8787"

        session = get_session()
        try:
            settings = AppSettings.get_settings(session)
            settings.api_server_url = api_url
            settings.auto_scrape_enabled = auto_scrape
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


class EditSourceScreen(ModalScreen[bool]):
    """Modal screen for editing a scraping source with dynamic config fields."""

    CSS = """
    EditSourceScreen {
        align: center middle;
    }

    #edit-source-container {
        width: 80;
        height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #edit-source-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
        color: $primary;
    }

    .section-header {
        margin-top: 1;
        text-style: bold;
        color: $secondary;
    }

    #edit-source-scroll {
        height: 1fr;
    }

    #config-fields {
        border: solid $secondary;
        padding: 1;
        margin-top: 1;
    }

    #edit-source-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    Select {
        width: 100%;
    }

    TextArea {
        height: 5;
    }
    """

    def __init__(self, source_id: Optional[str] = None) -> None:
        """Initialize with optional source ID for editing."""
        super().__init__()
        self.source_id = source_id
        self.source: Optional[ScraperSource] = None
        self.current_type = "hiring_cafe"
        if source_id:
            session = get_session()
            try:
                self.source = session.query(ScraperSource).filter(ScraperSource.id == source_id).first()
                if self.source:
                    self.current_type = self.source.source_type
            finally:
                session.close()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        title = "Edit Scraping Source" if self.source else "Add Scraping Source"
        
        source_type_options = [(v, k) for k, v in ScraperSource.SOURCE_TYPES.items()]
        schedule_options = [(s.capitalize(), s) for s in ScraperSource.SCHEDULE_OPTIONS]
        
        with Vertical(id="edit-source-container"):
            yield Label(title, id="edit-source-title")
            
            with VerticalScroll(id="edit-source-scroll"):
                yield Label("Source Name:", classes="field-label")
                yield Input(
                    id="name-input",
                    placeholder="My Scraping Source",
                    value=self.source.name if self.source else "",
                )
                
                yield Label("Source Type:", classes="field-label")
                yield Select(
                    source_type_options,
                    id="type-select",
                    value=self.source.source_type if self.source else "hiring_cafe",
                )
                
                yield Label("Schedule:", classes="field-label")
                yield Select(
                    schedule_options,
                    id="schedule-select",
                    value=self.source.schedule if self.source else "manual",
                )
                
                yield Label("Enabled:", classes="field-label")
                with Horizontal():
                    yield Switch(id="enabled-switch", value=self.source.enabled if self.source else True)
                    yield Label("Source is active")
                
                # Dynamic config fields container
                yield Label("── Configuration ──", classes="section-header")
                yield Container(id="config-fields")
            
            with Horizontal(id="edit-source-buttons"):
                yield Button("Save", id="save", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    async def on_mount(self) -> None:
        """Called when mounted."""
        await self._rebuild_config_fields(self.current_type)

    @on(Select.Changed, "#type-select")
    async def type_changed(self, event: Select.Changed) -> None:
        """Handle source type change - rebuild config fields."""
        if event.value:
            self.current_type = str(event.value)
            await self._rebuild_config_fields(self.current_type)

    async def _rebuild_config_fields(self, source_type: str) -> None:
        """Rebuild the config fields based on source type."""
        container = self.query_one("#config-fields", Container)
        await container.remove_children()
        
        fields = ScraperSource.CONFIG_FIELDS.get(source_type, [])
        config = self.source.get_config() if self.source and self.source.source_type == source_type else {}
        
        for field in fields:
            name = field["name"]
            label = field["label"]
            field_type = field["type"]
            default = field.get("default", "")
            
            # Get current value from config or use default
            value = config.get(name, default)
            
            # Create label
            lbl = Label(f"{label}:", classes="field-label")
            container.mount(lbl)
            
            if field_type == "text":
                inp = Input(
                    id=f"config-{name}",
                    value=str(value) if value else "",
                    placeholder=str(default),
                )
                container.mount(inp)
            elif field_type == "number":
                inp = Input(
                    id=f"config-{name}",
                    value=str(value) if value else str(default),
                    placeholder=str(default),
                )
                container.mount(inp)
            elif field_type == "bool":
                sw = Switch(id=f"config-{name}", value=bool(value))
                container.mount(sw)
            elif field_type == "select":
                options = [(opt.replace("-", " ").title(), opt) for opt in field.get("options", [])]
                sel = Select(options, id=f"config-{name}", value=str(value) if value else str(default))
                container.mount(sel)
            elif field_type == "multiline":
                # For multiline, convert list to newline-separated string
                if isinstance(value, list):
                    value = "\n".join(value)
                inp = Input(
                    id=f"config-{name}",
                    value=str(value) if value else "",
                    placeholder="Enter values, comma-separated for multiple",
                )
                container.mount(inp)

    def _collect_config(self) -> dict:
        """Collect config values from the dynamic fields."""
        config = {}
        fields = ScraperSource.CONFIG_FIELDS.get(self.current_type, [])
        
        for field in fields:
            name = field["name"]
            field_type = field["type"]
            widget_id = f"#config-{name}"
            
            try:
                if field_type == "bool":
                    widget = self.query_one(widget_id, Switch)
                    config[name] = widget.value
                elif field_type == "select":
                    widget = self.query_one(widget_id, Select)
                    config[name] = str(widget.value)
                elif field_type == "number":
                    widget = self.query_one(widget_id, Input)
                    try:
                        config[name] = int(widget.value)
                    except ValueError:
                        config[name] = field.get("default", 0)
                elif field_type == "multiline":
                    widget = self.query_one(widget_id, Input)
                    # Split by comma or newline
                    value = widget.value.strip()
                    if value:
                        items = [v.strip() for v in value.replace("\n", ",").split(",") if v.strip()]
                        config[name] = items
                    else:
                        config[name] = []
                else:  # text
                    widget = self.query_one(widget_id, Input)
                    value = widget.value.strip()
                    # Handle comma-separated lists for certain fields
                    if name in ("experience_levels", "categories"):
                        config[name] = [v.strip() for v in value.split(",") if v.strip()]
                    else:
                        config[name] = value
            except Exception:
                # Field not found, use default
                config[name] = field.get("default", "")
        
        return config

    @on(Button.Pressed, "#save")
    def save_source(self) -> None:
        """Save the source."""
        name = self.query_one("#name-input", Input).value.strip()
        source_type = str(self.query_one("#type-select", Select).value)
        schedule = str(self.query_one("#schedule-select", Select).value)
        enabled = self.query_one("#enabled-switch", Switch).value
        
        if not name:
            return
        
        config = self._collect_config()
        
        session = get_session()
        try:
            if self.source_id:
                source = session.query(ScraperSource).filter(ScraperSource.id == self.source_id).first()
                if source:
                    source.name = name
                    source.source_type = source_type
                    source.schedule = schedule
                    source.enabled = enabled
                    source.set_config(config)
            else:
                source = ScraperSource(
                    name=name,
                    source_type=source_type,
                    schedule=schedule,
                    enabled=enabled,
                )
                source.set_config(config)
                session.add(source)
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


class JobTrackApp(App):
    """Main TUI application for job tracking."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
    }

    #filter-bar {
        height: 3;
        padding: 0 1;
        background: $surface;
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
        height: 1fr;
    }

    DataTable > .datatable--cursor {
        background: $primary;
    }

    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 0;
        height: 1fr;
    }

    ContentSwitcher {
        height: 1fr;
    }

    .tab-content {
        height: 1fr;
    }

    #profile-view {
        padding: 1;
        height: 1fr;
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

    #settings-view {
        padding: 1;
    }

    #settings-summary {
        height: auto;
        padding: 1;
        border: solid $secondary;
        margin-bottom: 1;
    }

    #settings-actions {
        height: 3;
    }

    #settings-actions Button {
        margin-right: 1;
    }

    #scrape-btn {
        margin-left: 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "open_link", "Open Link"),
        Binding("d", "view_details", "Details"),
        Binding("a", "context_action_a", "Apply/Add"),
        Binding("x", "remove_selected", "Remove"),
        Binding("p", "select_profile", "Profiles"),
        Binding("n", "add_profile", "New Profile"),
        Binding("f", "toggle_filter", "Toggle Filters"),
        Binding("slash", "search", "Search"),
        Binding("s", "scrape_sources", "Scrape Sources"),
        Binding("c", "hiring_cafe", "hiring.cafe"),
        Binding("g", "settings", "Settings"),
        Binding("t", "focus_table", "Focus Table"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("h", "tab_left", "Prev Tab", show=False),
        Binding("l", "tab_right", "Next Tab", show=False),
        Binding("left", "tab_left", "Prev Tab", show=False),
        Binding("right", "tab_right", "Next Tab", show=False),
        Binding("1", "switch_tab_jobs", "Jobs Tab", show=False),
        Binding("2", "switch_tab_history", "History Tab", show=False),
        Binding("3", "switch_tab_profiles", "Profiles Tab", show=False),
        Binding("4", "switch_tab_settings", "Settings Tab", show=False),
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
                with Vertical(id="main-container"):
                    with Horizontal(id="filter-bar"):
                        yield Label("Filters:")
                        yield Switch(id="new-grad-filter")
                        yield Label("New Grad")
                        yield Switch(id="applied-filter")
                        yield Label("Applied")
                        yield Switch(id="pending-filter")
                        yield Label("Pending")
                        yield Input(id="search-input", placeholder="Search...")
                        yield Button("Scrape", id="scrape-btn", variant="success")
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
            with TabPane("Settings", id="settings-tab"):
                with Vertical(id="settings-view"):
                    yield Static(id="settings-summary")
                    with Horizontal(id="settings-actions"):
                        yield Button("Edit Settings", id="edit-settings-btn", variant="primary")
                        yield Button("Manage Sources", id="manage-sources-btn", variant="success")
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Set the light theme
        self.theme = "textual-light"
        
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
        self.refresh_settings_summary()
        
        # Focus the job table for immediate navigation with j/k
        table.focus()
        
        # Set initial status bar
        self.update_status_bar_for_tab("jobs-tab")

    @on(TabbedContent.TabActivated)
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab change - update status bar."""
        self.update_status_bar_for_tab(str(event.pane.id))

    def update_status_bar_for_tab(self, tab_id: str) -> None:
        """Update status bar with context-sensitive keybindings."""
        common = "h/l tabs | t focus | q quit"
        
        if tab_id == "jobs-tab":
            hints = "enter open | a mark applied | d details | s scrape | c hiring.cafe | f filter | / search"
        elif tab_id == "history-tab":
            hints = "enter open | a add application | x remove | d details"
        elif tab_id == "profiles-tab":
            hints = "n new profile | enter select | p switch profile"
        elif tab_id == "settings-tab":
            hints = "g edit settings | s manage sources"
        else:
            hints = "r refresh"
        
        self.query_one("#status-bar", Static).update(f"{hints} | {common}")

    def refresh_settings_summary(self) -> None:
        """Refresh the settings summary display."""
        session = get_session()
        try:
            settings = AppSettings.get_settings(session)
            sources = session.query(ScraperSource).all()
            
            enabled_sources = [s for s in sources if s.enabled]
            scheduled_sources = [s for s in sources if s.schedule != "manual"]
            
            lines = [
                "[bold]API Server Settings[/bold]",
                f"  Server URL: {settings.api_server_url}",
                f"  Auto-Scrape: {'Enabled' if settings.auto_scrape_enabled else 'Disabled'}",
                "",
                "[bold]Scraping Sources[/bold]",
                f"  Total Sources: {len(sources)}",
                f"  Enabled: {len(enabled_sources)}",
                f"  Scheduled (non-manual): {len(scheduled_sources)}",
                "",
                "[bold]Quick Actions[/bold]",
                "  Press 's' to open scraping sources dropdown",
                "  Press 'g' to edit settings",
            ]
            
            self.query_one("#settings-summary", Static).update("\n".join(lines))
        finally:
            session.close()

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
                        profile_name = profile.profile_name

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
                    f"{profile.profile_name} ({profile.get_full_name()}) - {resume_count} resumes",
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
            details.append(f"[bold]Profile:[/bold] {profile.profile_name}")
            details.append(f"[bold]Name:[/bold] {profile.get_full_name()}")
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

    @on(DataTable.RowSelected, "#job-table")
    def job_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter key / row selection on job table - open the job link."""
        self.action_open_job()

    @on(DataTable.RowSelected, "#history-table")
    def history_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter key / row selection on history table - open the job link."""
        job = self.get_selected_applied_job()
        if job and job.get("apply_url"):
            webbrowser.open(job["apply_url"])
            self.update_status(f"Opened: {job['title']}")

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
    def add_application_pressed(self) -> None:
        """Handle add application button."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_history()
                self.update_status("Application added")
        self.push_screen(AddApplicationScreen(), on_result)

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
    def new_profile_pressed(self) -> None:
        """Handle new profile button."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_profiles()
                self.update_status("Profile created")
        self.push_screen(ProfileEditScreen(), on_result)

    @on(Button.Pressed, "#edit-profile-btn")
    def edit_profile_pressed(self) -> None:
        """Handle edit profile button."""
        if not self.selected_profile_id:
            self.update_status("No profile selected")
            return
        def on_result(result: bool) -> None:
            if result:
                self.refresh_profiles()
                self._update_profile_details()
                self.update_status("Profile updated")
        self.push_screen(ProfileEditScreen(self.selected_profile_id), on_result)

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
    def upload_resume_pressed(self) -> None:
        """Handle upload resume button."""
        if not self.selected_profile_id:
            self.update_status("No profile selected")
            return
        def on_result(result: bool) -> None:
            if result:
                self.refresh_profiles()
                self._update_profile_details()
                self.update_status("Resume uploaded")
        self.push_screen(ResumeUploadScreen(self.selected_profile_id), on_result)

    @on(Button.Pressed, "#scrape-btn")
    def scrape_btn_pressed(self) -> None:
        """Handle scrape button in filter bar."""
        self.action_scrape_sources()

    @on(Button.Pressed, "#edit-settings-btn")
    def edit_settings_pressed(self) -> None:
        """Handle edit settings button."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_settings_summary()
                self.update_status("Settings saved")
        self.push_screen(SettingsScreen(), on_result)

    @on(Button.Pressed, "#manage-sources-btn")
    def manage_sources_pressed(self) -> None:
        """Handle manage sources button."""
        def on_result(result: bool) -> None:
            self.refresh_settings_summary()
            if result:
                self.refresh_jobs()
                self.update_status("Scraping complete")
        self.push_screen(ScrapingSourcesScreen(), on_result)

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
            else:
                # Try to find and move cursor in the active tab's table
                tabs = self.query_one(TabbedContent)
                if tabs.active == "jobs-tab":
                    table = self.query_one("#job-table", DataTable)
                    table.focus()
                    table.action_cursor_down()
                elif tabs.active == "history-tab":
                    table = self.query_one("#history-table", DataTable)
                    table.focus()
                    table.action_cursor_down()
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        """Move cursor up (vim k key)."""
        try:
            focused = self.focused
            if isinstance(focused, DataTable):
                focused.action_cursor_up()
            else:
                # Try to find and move cursor in the active tab's table
                tabs = self.query_one(TabbedContent)
                if tabs.active == "jobs-tab":
                    table = self.query_one("#job-table", DataTable)
                    table.focus()
                    table.action_cursor_up()
                elif tabs.active == "history-tab":
                    table = self.query_one("#history-table", DataTable)
                    table.focus()
                    table.action_cursor_up()
        except Exception:
            pass

    def action_switch_tab_jobs(self) -> None:
        """Switch to jobs tab."""
        self.query_one(TabbedContent).active = "jobs-tab"
        self.update_status_bar_for_tab("jobs-tab")

    def action_switch_tab_history(self) -> None:
        """Switch to history tab."""
        self.query_one(TabbedContent).active = "history-tab"
        self.update_status_bar_for_tab("history-tab")

    def action_switch_tab_profiles(self) -> None:
        """Switch to profiles tab."""
        self.query_one(TabbedContent).active = "profiles-tab"
        self.update_status_bar_for_tab("profiles-tab")

    def action_switch_tab_settings(self) -> None:
        """Switch to settings tab."""
        self.query_one(TabbedContent).active = "settings-tab"
        self.update_status_bar_for_tab("settings-tab")

    def action_tab_left(self) -> None:
        """Switch to previous tab (vi-like h or left arrow)."""
        tabs = self.query_one(TabbedContent)
        tab_order = ["jobs-tab", "history-tab", "profiles-tab", "settings-tab"]
        try:
            current_idx = tab_order.index(tabs.active)
            new_idx = (current_idx - 1) % len(tab_order)
            tabs.active = tab_order[new_idx]
            self.update_status_bar_for_tab(tab_order[new_idx])
        except ValueError:
            tabs.active = "jobs-tab"
            self.update_status_bar_for_tab("jobs-tab")

    def action_tab_right(self) -> None:
        """Switch to next tab (vi-like l or right arrow)."""
        tabs = self.query_one(TabbedContent)
        tab_order = ["jobs-tab", "history-tab", "profiles-tab", "settings-tab"]
        try:
            current_idx = tab_order.index(tabs.active)
            new_idx = (current_idx + 1) % len(tab_order)
            tabs.active = tab_order[new_idx]
            self.update_status_bar_for_tab(tab_order[new_idx])
        except ValueError:
            tabs.active = "jobs-tab"
            self.update_status_bar_for_tab("jobs-tab")

    def action_focus_table(self) -> None:
        """Focus on the main table of the current tab."""
        try:
            tabs = self.query_one(TabbedContent)
            if tabs.active == "jobs-tab":
                table = self.query_one("#job-table", DataTable)
                table.focus()
            elif tabs.active == "history-tab":
                table = self.query_one("#history-table", DataTable)
                table.focus()
            elif tabs.active == "profiles-tab":
                profile_list = self.query_one("#profile-list", OptionList)
                profile_list.focus()
            elif tabs.active == "settings-tab":
                # Focus settings summary or first focusable element
                pass
        except Exception:
            pass

    def action_open_link(self) -> None:
        """Open link - context aware based on current tab."""
        tabs = self.query_one(TabbedContent)
        if tabs.active == "jobs-tab":
            self.action_open_job()
        elif tabs.active == "history-tab":
            job = self.get_selected_applied_job()
            if job and job.get("apply_url"):
                webbrowser.open(job["apply_url"])
                self.update_status(f"Opened: {job['title']}")

    def action_context_action_a(self) -> None:
        """Context-aware 'a' action - mark applied on jobs, add application on history."""
        tabs = self.query_one(TabbedContent)
        if tabs.active == "jobs-tab":
            self.action_mark_applied()
        elif tabs.active == "history-tab":
            self.action_add_application()

    def action_add_application(self) -> None:
        """Add a new application manually."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_history()
                self.update_status("Application added")
        self.push_screen(AddApplicationScreen(), on_result)

    def action_remove_selected(self) -> None:
        """Remove selected item - context aware based on current tab."""
        tabs = self.query_one(TabbedContent)
        if tabs.active == "history-tab":
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

    def action_mark_applied(self) -> None:
        """Mark job as applied with confirmation dialog."""
        job = self.get_selected_job()
        if not job:
            self.update_status("No job selected")
            return

        def on_result(applied: bool) -> None:
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

        self.push_screen(ConfirmApplyScreen(job["title"], job["company"]), on_result)

    def action_select_profile(self) -> None:
        """Select a profile for applications."""
        def on_result(profile_id: str | None) -> None:
            if profile_id:
                self.selected_profile_id = profile_id
                session = get_session()
                try:
                    profile = session.query(Profile).filter(Profile.id == profile_id).first()
                    if profile:
                        self.update_status(f"Selected profile: {profile.profile_name}")
                finally:
                    session.close()
        self.push_screen(ProfileSelectScreen(), on_result)

    def action_add_profile(self) -> None:
        """Add a new profile."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_profiles()
                self.update_status("Profile added")
        self.push_screen(ProfileEditScreen(), on_result)

    def action_scrape_sources(self) -> None:
        """Open scrape sources modal with dropdown of implemented sources."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_jobs()
                self.refresh_settings_summary()
        self.push_screen(ScrapingSourcesScreen(), on_result)

    def action_scrape(self) -> None:
        """Open old scrape modal (kept for backwards compatibility)."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_jobs()
        self.push_screen(ScrapeScreen(), on_result)

    def action_settings(self) -> None:
        """Open settings modal."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_settings_summary()
                self.update_status("Settings saved")
        self.push_screen(SettingsScreen(), on_result)

    def action_hiring_cafe(self) -> None:
        """Open hiring.cafe search modal."""
        def on_result(result: bool) -> None:
            if result:
                self.refresh_jobs()
        self.push_screen(HiringCafeSearchScreen(), on_result)

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
