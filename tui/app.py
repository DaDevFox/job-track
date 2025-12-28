"""Terminal User Interface for job tracking application."""
import asyncio
import httpx
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Button, DataTable, Static, Input, Select, TextArea
from textual.binding import Binding
from textual.screen import Screen
from rich.text import Text
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000"


class JobListScreen(Screen):
    """Screen for displaying job listings."""
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "scrape", "Scrape Jobs"),
        Binding("a", "applications", "Applications"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose the job list screen."""
        yield Header()
        yield Container(
            Static("Job Listings", classes="title"),
            Horizontal(
                Button("Refresh", id="refresh_btn", variant="primary"),
                Button("Scrape Jobs", id="scrape_btn", variant="success"),
                Button("View Applications", id="apps_btn", variant="default"),
                classes="button_bar"
            ),
            DataTable(id="jobs_table"),
            classes="main_container"
        )
        yield Footer()
    
    async def on_mount(self) -> None:
        """Setup the job list table."""
        table = self.query_one("#jobs_table", DataTable)
        table.add_columns("ID", "Title", "Company", "Location", "URL")
        table.cursor_type = "row"
        await self.load_jobs()
    
    async def load_jobs(self) -> None:
        """Load jobs from the API."""
        table = self.query_one("#jobs_table", DataTable)
        table.clear()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{API_BASE_URL}/jobs")
                if response.status_code == 200:
                    jobs = response.json()
                    for job in jobs:
                        table.add_row(
                            str(job["id"]),
                            job["title"][:30],
                            job["company"][:20],
                            job["location"][:20] if job["location"] else "N/A",
                            job["url"][:40]
                        )
                    self.notify(f"Loaded {len(jobs)} jobs")
                else:
                    self.notify(f"Error loading jobs: {response.status_code}", severity="error")
        except Exception as e:
            logger.error(f"Error loading jobs: {e}")
            self.notify(f"Error: {str(e)}", severity="error")
    
    async def action_refresh(self) -> None:
        """Refresh the job list."""
        await self.load_jobs()
    
    async def action_scrape(self) -> None:
        """Scrape new jobs."""
        self.notify("Scraping jobs...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{API_BASE_URL}/scrape",
                    params={"search_term": "software engineer", "location": ""}
                )
                if response.status_code == 200:
                    result = response.json()
                    self.notify(f"Scraped: {result['message']}")
                    await self.load_jobs()
                else:
                    self.notify(f"Error scraping: {response.status_code}", severity="error")
        except Exception as e:
            logger.error(f"Error scraping jobs: {e}")
            self.notify(f"Error: {str(e)}", severity="error")
    
    def action_applications(self) -> None:
        """Switch to applications screen."""
        self.app.push_screen(ApplicationsScreen())
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh_btn":
            await self.action_refresh()
        elif event.button.id == "scrape_btn":
            await self.action_scrape()
        elif event.button.id == "apps_btn":
            self.action_applications()


class ApplicationsScreen(Screen):
    """Screen for viewing and managing applications."""
    
    BINDINGS = [
        Binding("q", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
        Binding("n", "new_application", "New Application"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose the applications screen."""
        yield Header()
        yield Container(
            Static("My Applications", classes="title"),
            Horizontal(
                Button("Refresh", id="refresh_apps_btn", variant="primary"),
                Button("New Application", id="new_app_btn", variant="success"),
                Button("Back to Jobs", id="back_btn", variant="default"),
                classes="button_bar"
            ),
            DataTable(id="apps_table"),
            classes="main_container"
        )
        yield Footer()
    
    async def on_mount(self) -> None:
        """Setup the applications table."""
        table = self.query_one("#apps_table", DataTable)
        table.add_columns("ID", "Title", "Company", "Status", "Applied Date")
        table.cursor_type = "row"
        await self.load_applications()
    
    async def load_applications(self) -> None:
        """Load applications from the API."""
        table = self.query_one("#apps_table", DataTable)
        table.clear()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{API_BASE_URL}/applications")
                if response.status_code == 200:
                    applications = response.json()
                    for app in applications:
                        applied_date = datetime.fromisoformat(
                            app["applied_date"].replace('Z', '+00:00')
                        )
                        table.add_row(
                            str(app["id"]),
                            app["job_title"][:30],
                            app["company"][:20],
                            app["status"],
                            applied_date.strftime("%Y-%m-%d")
                        )
                    self.notify(f"Loaded {len(applications)} applications")
                else:
                    self.notify(f"Error loading applications: {response.status_code}", 
                              severity="error")
        except Exception as e:
            logger.error(f"Error loading applications: {e}")
            self.notify(f"Error: {str(e)}", severity="error")
    
    async def action_refresh(self) -> None:
        """Refresh the applications list."""
        await self.load_applications()
    
    def action_new_application(self) -> None:
        """Open new application form."""
        self.app.push_screen(NewApplicationScreen())
    
    def action_back(self) -> None:
        """Go back to job list."""
        self.app.pop_screen()
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh_apps_btn":
            await self.action_refresh()
        elif event.button.id == "new_app_btn":
            self.action_new_application()
        elif event.button.id == "back_btn":
            self.action_back()


class NewApplicationScreen(Screen):
    """Screen for creating a new application."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose the new application form."""
        yield Header()
        yield ScrollableContainer(
            Static("New Application", classes="title"),
            Vertical(
                Static("Job Title:"),
                Input(placeholder="e.g., Senior Software Engineer", id="job_title"),
                Static("Company:"),
                Input(placeholder="e.g., Tech Corp", id="company"),
                Static("Location:"),
                Input(placeholder="e.g., San Francisco, CA", id="location"),
                Static("Job URL:"),
                Input(placeholder="https://example.com/job", id="job_url"),
                Static("Status:"),
                Select([
                    ("Pending", "pending"),
                    ("Applied", "applied"),
                    ("Interview", "interview"),
                    ("Rejected", "rejected"),
                    ("Accepted", "accepted"),
                ], id="status", value="pending"),
                Static("Notes:"),
                TextArea(id="notes"),
                Horizontal(
                    Button("Submit", id="submit_btn", variant="success"),
                    Button("Cancel", id="cancel_btn", variant="default"),
                    classes="button_bar"
                ),
                classes="form_container"
            )
        )
        yield Footer()
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "submit_btn":
            await self.submit_application()
        elif event.button.id == "cancel_btn":
            self.action_cancel()
    
    async def submit_application(self) -> None:
        """Submit the new application."""
        job_title = self.query_one("#job_title", Input).value
        company = self.query_one("#company", Input).value
        location = self.query_one("#location", Input).value
        job_url = self.query_one("#job_url", Input).value
        status = self.query_one("#status", Select).value
        notes = self.query_one("#notes", TextArea).text
        
        if not job_title or not company:
            self.notify("Job title and company are required", severity="error")
            return
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{API_BASE_URL}/applications",
                    json={
                        "job_title": job_title,
                        "company": company,
                        "location": location or None,
                        "job_url": job_url or None,
                        "status": status,
                        "notes": notes or None,
                        "cover_letter": False
                    }
                )
                if response.status_code == 200:
                    self.notify("Application created successfully")
                    self.app.pop_screen()
                else:
                    self.notify(f"Error creating application: {response.status_code}", 
                              severity="error")
        except Exception as e:
            logger.error(f"Error creating application: {e}")
            self.notify(f"Error: {str(e)}", severity="error")
    
    def action_cancel(self) -> None:
        """Cancel and go back."""
        self.app.pop_screen()


class JobTrackApp(App):
    """Main application for job tracking."""
    
    CSS = """
    .title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $boost;
    }
    
    .button_bar {
        height: auto;
        padding: 1;
    }
    
    .main_container {
        height: 100%;
    }
    
    .form_container {
        padding: 1;
    }
    
    DataTable {
        height: 100%;
    }
    
    Button {
        margin: 0 1;
    }
    
    Input, TextArea, Select {
        margin: 0 0 1 0;
    }
    """
    
    TITLE = "Job Track"
    
    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(JobListScreen())


def main():
    """Run the TUI application."""
    app = JobTrackApp()
    app.run()


if __name__ == "__main__":
    main()
