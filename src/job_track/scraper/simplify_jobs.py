"""SimplifyJobs GitHub scraper for new grad positions.

This module scrapes job listings from the SimplifyJobs New-Grad-Positions
GitHub repository README, which maintains a curated list of software
engineering new grad roles.

Source: https://github.com/SimplifyJobs/New-Grad-Positions
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .scraper import ScrapedJob, JobScraper


# Raw GitHub URL for the README
RAW_README_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
GITHUB_REPO_URL = "https://github.com/SimplifyJobs/New-Grad-Positions"


@dataclass
class SimplifyJobsConfig:
    """Configuration for SimplifyJobs scraper.
    
    Attributes:
        include_inactive: Whether to include inactive/closed job listings.
        categories: List of job categories to scrape.
        location_filter: Optional filter for specific locations.
        max_age_days: Only include jobs posted within this many days.
    """
    include_inactive: bool = False
    categories: list[str] = field(default_factory=lambda: ["software-engineering"])
    location_filter: Optional[str] = None
    max_age_days: Optional[int] = None
    
    # Available category mappings
    CATEGORY_HEADERS = {
        "software-engineering": "💻 Software Engineering New Grad Roles",
        "product-management": "📱 Product Management New Grad Roles",
        "data-science": "🤖 Data Science, AI & Machine Learning New Grad Roles",
        "quantitative-finance": "📈 Quantitative Finance New Grad Roles",
        "hardware-engineering": "🔧 Hardware Engineering New Grad Roles",
        "other": "💼 Other New Grad Roles",
    }
    
    @classmethod
    def software_engineering(cls) -> "SimplifyJobsConfig":
        """Create a config for software engineering roles only."""
        return cls(
            include_inactive=False,
            categories=["software-engineering"],
            max_age_days=30,
        )
    
    @classmethod
    def all_categories(cls) -> "SimplifyJobsConfig":
        """Create a config for all job categories."""
        return cls(
            include_inactive=False,
            categories=list(cls.CATEGORY_HEADERS.keys()),
            max_age_days=None,
        )


class SimplifyJobsScraper(JobScraper):
    """Scraper for SimplifyJobs New-Grad-Positions GitHub repository.
    
    This scraper fetches and parses the README.md from the SimplifyJobs
    GitHub repository to extract new grad job listings.
    """
    
    def __init__(self, config: Optional[SimplifyJobsConfig] = None):
        """Initialize the SimplifyJobs scraper.
        
        Args:
            config: Scraper configuration. Defaults to software engineering roles.
        """
        super().__init__(filter_new_grad=True)  # All jobs here are new-grad
        self.config = config or SimplifyJobsConfig.software_engineering()
    
    def _parse_age_to_days(self, age_str: str) -> Optional[int]:
        """Convert age string like '5d', '1mo', '2mo' to days.
        
        Args:
            age_str: Age string from the table (e.g., "5d", "1mo", "2mo")
            
        Returns:
            Number of days, or None if parsing fails.
        """
        age_str = age_str.strip().lower()
        
        # Match patterns like "5d", "1mo", "2mo"
        day_match = re.match(r"(\d+)d", age_str)
        if day_match:
            return int(day_match.group(1))
        
        month_match = re.match(r"(\d+)mo", age_str)
        if month_match:
            return int(month_match.group(1)) * 30  # Approximate
        
        return None
    
    def _extract_apply_url(self, cell_html: str) -> Optional[str]:
        """Extract apply URL from the application cell.
        
        Args:
            cell_html: HTML content of the application cell.
            
        Returns:
            Apply URL or None if not found/closed.
        """
        # Check if job is closed (lock emoji)
        if "🔒" in cell_html:
            return None
        
        # Parse HTML to find links
        soup = BeautifulSoup(cell_html, "html.parser")
        
        # Look for apply links (the main apply button, not Simplify)
        for link in soup.find_all("a"):
            href = link.get("href", "")
            # Prefer direct apply links, skip Simplify redirect links
            if href and "simplify.jobs/p/" not in href:
                # Clean up the URL
                if href.startswith("http"):
                    return href
        
        # If no direct link, try Simplify links
        for link in soup.find_all("a"):
            href = link.get("href", "")
            if href and href.startswith("http"):
                return href
        
        return None
    
    def _extract_company_info(self, cell_html: str) -> tuple[str, bool]:
        """Extract company name and FAANG+ status from company cell.
        
        Args:
            cell_html: HTML content of the company cell.
            
        Returns:
            Tuple of (company_name, is_faang_plus)
        """
        soup = BeautifulSoup(cell_html, "html.parser")
        
        # Get text content
        text = soup.get_text(strip=True)
        
        # Check for FAANG+ indicator
        is_faang = "🔥" in text
        
        # Check for continuation row (↳ symbol)
        is_continuation = text.startswith("↳")
        
        # Clean company name
        company = text.replace("🔥", "").replace("↳", "").strip()
        
        # Try to get company from link if available
        link = soup.find("a")
        if link:
            link_text = link.get_text(strip=True)
            company = link_text.replace("🔥", "").strip()
        
        return company, is_faang, is_continuation
    
    def _extract_role_info(self, cell_html: str) -> tuple[str, list[str]]:
        """Extract role title and special tags from role cell.
        
        Args:
            cell_html: HTML content of the role cell.
            
        Returns:
            Tuple of (role_title, tags)
        """
        soup = BeautifulSoup(cell_html, "html.parser")
        text = soup.get_text(strip=True)
        
        tags = []
        
        # Check for special indicators
        if "🛂" in text:
            tags.append("no-sponsorship")
            text = text.replace("🛂", "")
        
        if "🇺🇸" in text:
            tags.append("us-citizenship-required")
            text = text.replace("🇺🇸", "")
        
        if "🎓" in text:
            tags.append("advanced-degree")
            text = text.replace("🎓", "")
        
        return text.strip(), tags
    
    def _extract_location(self, cell_html: str) -> str:
        """Extract location from location cell.
        
        Args:
            cell_html: HTML content of the location cell.
            
        Returns:
            Location string.
        """
        soup = BeautifulSoup(cell_html, "html.parser")
        
        # Check for details/summary (multiple locations)
        details = soup.find("details")
        if details:
            summary = details.find("summary")
            if summary:
                # Get summary text and full content
                summary_text = summary.get_text(strip=True)
                # Get all location text
                full_text = details.get_text(strip=True)
                return full_text
        
        # Simple location
        text = soup.get_text(strip=True)
        # Clean up <br> represented as multiple locations
        return text.replace("</br>", ", ").strip()
    
    def _parse_table(self, table_html: str, category: str) -> list[ScrapedJob]:
        """Parse a job listing table from the README.
        
        Args:
            table_html: HTML of the table element.
            category: Category name for tagging.
            
        Returns:
            List of ScrapedJob objects.
        """
        soup = BeautifulSoup(table_html, "html.parser")
        jobs = []
        
        # Track the last company for continuation rows
        last_company = ""
        last_is_faang = False
        
        # Find all table rows (skip header)
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue  # Skip invalid rows
            
            try:
                # Parse each cell
                company, is_faang, is_continuation = self._extract_company_info(str(cells[0]))
                
                # Handle continuation rows
                if is_continuation or not company:
                    company = last_company
                    is_faang = last_is_faang
                else:
                    last_company = company
                    last_is_faang = is_faang
                
                role_title, role_tags = self._extract_role_info(str(cells[1]))
                location = self._extract_location(str(cells[2]))
                apply_url = self._extract_apply_url(str(cells[3]))
                
                # Get age if available
                age_str = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                days_old = self._parse_age_to_days(age_str)
                
                # Skip closed jobs if not including inactive
                if not apply_url and not self.config.include_inactive:
                    continue
                
                # Skip if too old
                if self.config.max_age_days and days_old:
                    if days_old > self.config.max_age_days:
                        continue
                
                # Apply location filter if set
                if self.config.location_filter:
                    if self.config.location_filter.lower() not in location.lower():
                        continue
                
                # Build tags
                tags = ["new-grad", category] + role_tags
                if is_faang:
                    tags.append("faang+")
                if not apply_url:
                    tags.append("closed")
                
                # Create job object
                job = ScrapedJob(
                    title=role_title,
                    company=company,
                    location=location if location else None,
                    description=None,  # No description in the table
                    apply_url=apply_url or "",
                    source_url=GITHUB_REPO_URL,
                    tags=tags,
                )
                
                jobs.append(job)
                
            except Exception as e:
                # Skip malformed rows
                continue
        
        return jobs
    
    async def scrape(self) -> list[ScrapedJob]:
        """Scrape job listings from the SimplifyJobs GitHub repository.
        
        Returns:
            List of ScrapedJob objects.
        """
        all_jobs = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch the raw README
            response = await client.get(RAW_README_URL)
            response.raise_for_status()
            content = response.text
        
        # Parse the README HTML content
        # The README contains HTML tables embedded in markdown
        soup = BeautifulSoup(content, "html.parser")
        
        # Process each configured category
        for category in self.config.categories:
            header = SimplifyJobsConfig.CATEGORY_HEADERS.get(category)
            if not header:
                continue
            
            # Find the section for this category
            # Look for the table after the header
            # Since we're parsing raw markdown, we need to find tables
            
            # Find all tables in the document
            tables = soup.find_all("table")
            
            for table in tables:
                # Parse the table
                jobs = self._parse_table(str(table), category)
                all_jobs.extend(jobs)
        
        return all_jobs
    
    def scrape_sync(self) -> list[ScrapedJob]:
        """Synchronous wrapper for scrape().
        
        Returns:
            List of ScrapedJob objects.
        """
        return asyncio.run(self.scrape())


async def scrape_simplify_jobs(
    config: Optional[SimplifyJobsConfig] = None,
) -> list[ScrapedJob]:
    """Convenience function to scrape SimplifyJobs.
    
    Args:
        config: Optional scraper configuration.
        
    Returns:
        List of ScrapedJob objects.
    """
    scraper = SimplifyJobsScraper(config)
    return await scraper.scrape()


def scrape_simplify_jobs_sync(
    config: Optional[SimplifyJobsConfig] = None,
) -> list[ScrapedJob]:
    """Synchronous convenience function to scrape SimplifyJobs.
    
    Args:
        config: Optional scraper configuration.
        
    Returns:
        List of ScrapedJob objects.
    """
    return asyncio.run(scrape_simplify_jobs(config))
