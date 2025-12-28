"""Job scraper using Playwright and BeautifulSoup.

This module provides scraping functionality for extracting job listings
from various company career pages.
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString

# Playwright is optional - may not be installed in all environments
try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class ScrapedJob:
    """Represents a scraped job listing."""

    title: str
    company: str
    location: Optional[str]
    description: Optional[str]
    apply_url: str
    source_url: str
    tags: list[str]

    def generate_id(self) -> str:
        """Generate a unique ID based on job attributes."""
        content = f"{self.company}|{self.title}|{self.apply_url}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class JobScraper:
    """Base class for job scraping."""

    def __init__(self, filter_new_grad: bool = False):
        """Initialize scraper.

        Args:
            filter_new_grad: If True, only return jobs tagged as new-grad.
        """
        self.filter_new_grad = filter_new_grad
        self.new_grad_keywords = [
            "new grad",
            "new graduate",
            "entry level",
            "entry-level",
            "junior",
            "associate",
            "early career",
            "university grad",
            "recent graduate",
            "0-2 years",
            "0-1 years",
            "fresh grad",
            "campus",
        ]

    def _is_new_grad_job(self, title: str, description: Optional[str] = None) -> bool:
        """Check if a job is a new-grad position."""
        text = title.lower()
        if description:
            text += " " + description.lower()

        return any(keyword in text for keyword in self.new_grad_keywords)

    def _extract_company_from_url(self, url: str) -> str:
        """Extract company name from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove common prefixes/suffixes
        domain = re.sub(r"^(www\.|jobs\.|careers\.)", "", domain)
        domain = re.sub(r"\.(com|org|io|co|net|edu).*$", "", domain)
        # Capitalize
        return domain.replace("-", " ").title()

    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """Clean and normalize text."""
        if not text:
            return None
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text.strip())
        return text

    def _extract_location(self, soup: BeautifulSoup) -> Optional[str]:
        """Try to extract location from page content."""
        # Common location patterns
        location_selectors = [
            "[class*='location']",
            "[class*='Location']",
            "[data-testid*='location']",
            ".job-location",
            ".location",
            "span.location",
            "div.location",
        ]

        for selector in location_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = self._clean_text(elem.get_text())
                if text and len(text) < 200:  # Reasonable location length
                    return text

        return None


class PlaywrightScraper(JobScraper):
    """Job scraper using Playwright for JavaScript-rendered pages."""

    async def scrape_page(self, url: str) -> list[ScrapedJob]:
        """Scrape jobs from a single page.

        Args:
            url: URL to scrape.

        Returns:
            List of scraped jobs.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait a bit for dynamic content
                await asyncio.sleep(2)

                html = await page.content()
                return self._parse_html(html, url)
            finally:
                await browser.close()

    async def scrape_urls(self, urls: list[str]) -> list[ScrapedJob]:
        """Scrape jobs from multiple URLs.

        Args:
            urls: List of URLs to scrape.

        Returns:
            List of all scraped jobs.
        """
        all_jobs = []
        for url in urls:
            try:
                jobs = await self.scrape_page(url)
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"Error scraping {url}: {e}")
        return all_jobs

    def _parse_html(self, html: str, source_url: str) -> list[ScrapedJob]:
        """Parse HTML content for job listings."""
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        # Try to find job listing containers
        job_containers = self._find_job_containers(soup)

        for container in job_containers:
            job = self._parse_job_container(container, source_url)
            if job:
                if not self.filter_new_grad or self._is_new_grad_job(
                    job.title, job.description
                ):
                    jobs.append(job)

        # If no structured containers found, try to parse as single job page
        if not jobs:
            job = self._parse_single_job_page(soup, source_url)
            if job:
                if not self.filter_new_grad or self._is_new_grad_job(
                    job.title, job.description
                ):
                    jobs.append(job)

        return jobs

    def _find_job_containers(self, soup: BeautifulSoup) -> list:
        """Find job listing containers in the page."""
        # Common job listing container patterns
        selectors = [
            "[class*='job-card']",
            "[class*='JobCard']",
            "[class*='job-listing']",
            "[class*='JobListing']",
            "[class*='job-row']",
            "[class*='JobRow']",
            "[class*='posting']",
            "[data-job-id]",
            "[data-testid*='job']",
            "li[class*='job']",
            "article[class*='job']",
            "div[class*='job'][class*='item']",
        ]

        for selector in selectors:
            containers = soup.select(selector)
            if len(containers) > 1:  # Found multiple job listings
                return containers

        return []

    def _parse_job_container(
        self, container, source_url: str
    ) -> Optional[ScrapedJob]:
        """Parse a single job container element."""
        # Find title
        title = None
        title_elem = container.select_one(
            "h2, h3, h4, [class*='title'], [class*='Title'], a[class*='job']"
        )
        if title_elem:
            title = self._clean_text(title_elem.get_text())

        if not title:
            return None

        # Find apply link
        apply_url = None
        link = container.select_one("a[href]")
        if link:
            href = link.get("href", "")
            apply_url = urljoin(source_url, href)

        if not apply_url:
            apply_url = source_url

        # Find location
        location = None
        location_elem = container.select_one(
            "[class*='location'], [class*='Location']"
        )
        if location_elem:
            location = self._clean_text(location_elem.get_text())

        # Find description/snippet
        description = None
        desc_elem = container.select_one(
            "[class*='description'], [class*='Description'], [class*='snippet']"
        )
        if desc_elem:
            description = self._clean_text(desc_elem.get_text())

        company = self._extract_company_from_url(source_url)

        # Determine tags
        tags = []
        if self._is_new_grad_job(title, description):
            tags.append("new-grad")

        return ScrapedJob(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
            source_url=source_url,
            tags=tags,
        )

    def _parse_single_job_page(
        self, soup: BeautifulSoup, source_url: str
    ) -> Optional[ScrapedJob]:
        """Parse a single job detail page."""
        # Find title from h1 or common patterns
        title = None
        title_selectors = [
            "h1[class*='title']",
            "h1[class*='Title']",
            "[class*='job-title']",
            "[class*='JobTitle']",
            "h1",
        ]
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = self._clean_text(elem.get_text())
                if title and len(title) < 200:  # Reasonable title length
                    break
                title = None

        if not title:
            return None

        # Find description
        description = None
        desc_selectors = [
            "[class*='description']",
            "[class*='Description']",
            "[class*='job-details']",
            "[class*='JobDetails']",
            "article",
            "main",
        ]
        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                description = self._clean_text(elem.get_text())
                if description and len(description) > 100:
                    break
                description = None

        location = self._extract_location(soup)
        company = self._extract_company_from_url(source_url)

        # Find apply button/link
        apply_url = source_url
        apply_selectors = [
            "a[class*='apply']",
            "a[class*='Apply']",
            "button[class*='apply']",
            "a[href*='apply']",
        ]
        for selector in apply_selectors:
            elem = soup.select_one(selector)
            if elem and elem.name == "a":
                href = elem.get("href", "")
                if href:
                    apply_url = urljoin(source_url, href)
                    break

        tags = []
        if self._is_new_grad_job(title, description):
            tags.append("new-grad")

        return ScrapedJob(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
            source_url=source_url,
            tags=tags,
        )


class SimpleScraper(JobScraper):
    """Simple HTTP-based scraper without JavaScript rendering.

    Uses requests and BeautifulSoup for faster scraping of static pages.
    """

    def scrape_page(self, url: str, html: str) -> list[ScrapedJob]:
        """Parse HTML content for job listings.

        Args:
            url: Source URL.
            html: HTML content to parse.

        Returns:
            List of scraped jobs.
        """
        soup = BeautifulSoup(html, "html.parser")
        # Use same parsing logic as Playwright scraper
        pw_scraper = PlaywrightScraper(filter_new_grad=self.filter_new_grad)
        return pw_scraper._parse_html(html, url)


# Helper function for synchronous usage
def scrape_jobs_sync(urls: list[str], filter_new_grad: bool = False) -> list[ScrapedJob]:
    """Synchronous wrapper for scraping jobs.

    Args:
        urls: List of URLs to scrape.
        filter_new_grad: If True, only return new-grad jobs.

    Returns:
        List of scraped jobs.
    """
    scraper = PlaywrightScraper(filter_new_grad=filter_new_grad)
    return asyncio.run(scraper.scrape_urls(urls))
