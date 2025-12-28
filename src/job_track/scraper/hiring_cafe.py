"""Hiring.cafe scraper using Playwright.

This module provides a specialized scraper for hiring.cafe, a modern job search
aggregator with filtering capabilities. This is the main scraper for pulling
job listings into the application.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlencode, urljoin

from .scraper import ScrapedJob, JobScraper

# Playwright is optional - may not be installed in all environments
try:
    from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class SearchConfig:
    """Configuration for hiring.cafe job searches.
    
    Attributes:
        query: Search query string (e.g., "software engineer").
        department: Department filter (e.g., "software-engineering").
        experience_levels: List of experience levels to filter by.
        location: Location to search in.
        remote_options: List of work modes ("remote", "hybrid", "onsite").
        date_posted_days: Only show jobs posted within N days.
        max_results: Maximum number of jobs to scrape.
    """
    query: str = "software engineer"
    department: Optional[str] = "software-engineering"
    experience_levels: list[str] = field(default_factory=lambda: ["entry-level", "internship"])
    location: str = "United States"
    remote_options: list[str] = field(default_factory=lambda: ["remote", "hybrid", "onsite"])
    date_posted_days: int = 30
    max_results: int = 100
    
    # Default profiles
    NEW_GRAD_SWE = None  # Will be set after class definition
    
    @classmethod
    def new_grad_software_engineer(cls) -> "SearchConfig":
        """Create a config optimized for new-grad software engineering roles."""
        return cls(
            query="software engineer",
            department="software-engineering",
            experience_levels=["entry-level", "internship"],
            location="United States",
            remote_options=["remote", "hybrid", "onsite"],
            date_posted_days=30,
            max_results=100,
        )
    
    @classmethod
    def intern_software_engineer(cls) -> "SearchConfig":
        """Create a config for software engineering internships."""
        return cls(
            query="software engineer intern",
            department="software-engineering",
            experience_levels=["internship"],
            location="United States",
            remote_options=["remote", "hybrid", "onsite"],
            date_posted_days=60,
            max_results=100,
        )


# Set the class attribute after class definition
SearchConfig.NEW_GRAD_SWE = SearchConfig.new_grad_software_engineer


class HiringCafeScraper(JobScraper):
    """Specialized scraper for hiring.cafe job listings.
    
    This scraper uses Playwright to render the JavaScript-heavy hiring.cafe
    website and extract job listings with their details.
    """
    
    BASE_URL = "https://hiring.cafe"
    SEARCH_URL = "https://hiring.cafe/search"
    
    def __init__(
        self,
        config: Optional[SearchConfig] = None,
        headless: bool = True,
        slow_mo: int = 0,
    ):
        """Initialize the hiring.cafe scraper.
        
        Args:
            config: Search configuration. Defaults to new-grad SWE search.
            headless: Run browser in headless mode.
            slow_mo: Slow down operations by specified milliseconds (for debugging).
        """
        super().__init__(filter_new_grad=True)
        self.config = config or SearchConfig.new_grad_software_engineer()
        self.headless = headless
        self.slow_mo = slow_mo
    
    def _build_search_url(self) -> str:
        """Build the search URL with query parameters."""
        params = {}
        
        # Add search query
        if self.config.query:
            params["q"] = self.config.query
        
        # Add department filter
        if self.config.department:
            params["departments"] = self.config.department
        
        # Add experience level filters
        if self.config.experience_levels:
            params["experience"] = ",".join(self.config.experience_levels)
        
        # Build URL
        if params:
            return f"{self.SEARCH_URL}?{urlencode(params)}"
        return self.SEARCH_URL
    
    async def scrape(self) -> list[ScrapedJob]:
        """Scrape job listings from hiring.cafe.
        
        Returns:
            List of scraped jobs matching the search criteria.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )
        
        jobs = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
            )
            
            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()
                
                # Navigate to search page
                search_url = self._build_search_url()
                print(f"🔍 Navigating to: {search_url}")
                
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for job listings to load
                await self._wait_for_jobs(page)
                
                # Scroll to load more jobs if needed
                jobs = await self._scrape_job_listings(page)
                
                print(f"📋 Scraped {len(jobs)} jobs from hiring.cafe")
                
            except PlaywrightTimeout as e:
                print(f"⏱️ Timeout while scraping: {e}")
            except Exception as e:
                print(f"❌ Error scraping hiring.cafe: {e}")
                import traceback
                traceback.print_exc()
            finally:
                await browser.close()
        
        return jobs
    
    async def _wait_for_jobs(self, page: Page, timeout: int = 30000) -> None:
        """Wait for job listings to appear on the page."""
        # Wait for either job cards or a "no results" message
        try:
            # Try waiting for job listing elements - look for viewjob links
            await page.wait_for_selector(
                "a[href*='/viewjob/']",
                timeout=timeout,
            )
            # Give extra time for job cards to fully render
            await asyncio.sleep(2)
        except PlaywrightTimeout:
            # Check if there's a "no jobs" message
            no_jobs = await page.query_selector("text=No jobs found")
            if no_jobs:
                print("📭 No jobs found matching criteria")
            else:
                print("⚠️ Could not find job listings - page structure may have changed")
    
    async def _scrape_job_listings(self, page: Page) -> list[ScrapedJob]:
        """Extract job listings from the page using JavaScript for better parsing."""
        jobs = []
        scraped_urls = set()  # Track duplicates
        
        # Scroll to load more jobs
        last_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 15
        
        while len(jobs) < self.config.max_results and scroll_attempts < max_scroll_attempts:
            # Use JavaScript to extract job data from the page structure
            job_data_list = await page.evaluate("""
                () => {
                    const jobs = [];
                    // Find all job posting links
                    const jobLinks = document.querySelectorAll('a[href*="/viewjob/"]');
                    
                    jobLinks.forEach(link => {
                        const href = link.getAttribute('href');
                        if (!href || href.includes('undefined')) return;
                        
                        // Get the text content from the link and nearby elements
                        // The job title is usually the first visible text in the link
                        const linkText = link.innerText.trim();
                        
                        // Try to find the parent job card container
                        let container = link;
                        for (let i = 0; i < 10; i++) {
                            if (container.parentElement) {
                                container = container.parentElement;
                            }
                        }
                        const cardText = container.innerText || '';
                        
                        // Skip if this looks like a navigation element
                        if (linkText === 'View all' || linkText === 'Job Posting' || 
                            linkText.includes('See views') || linkText.length < 3) {
                            return;
                        }
                        
                        jobs.push({
                            url: href,
                            linkText: linkText,
                            cardText: cardText.substring(0, 2000),  // Limit text length
                        });
                    });
                    
                    return jobs;
                }
            """)
            
            for job_data in job_data_list:
                if len(jobs) >= self.config.max_results:
                    break
                
                job_url = urljoin(self.BASE_URL, job_data['url'])
                
                if job_url in scraped_urls:
                    continue
                
                try:
                    job = self._parse_job_data(job_data, job_url)
                    if job and job.title and job.title != "Relevance" and len(job.title) > 2:
                        scraped_urls.add(job_url)
                        jobs.append(job)
                except Exception as e:
                    print(f"⚠️ Error parsing job data: {e}")
                    continue
            
            # Check if we got new jobs
            if len(jobs) == last_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_count = len(jobs)
            
            # Scroll down to load more
            if len(jobs) < self.config.max_results:
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1.5)  # Wait for content to load
        
        return jobs
    
    def _parse_job_data(self, job_data: dict, job_url: str) -> Optional[ScrapedJob]:
        """Parse job data extracted via JavaScript into a ScrapedJob."""
        link_text = job_data.get('linkText', '')
        card_text = job_data.get('cardText', '')
        
        # Split the card text into lines
        lines = [line.strip() for line in card_text.split('\n') if line.strip()]
        
        # Filter out navigation/UI elements
        filtered_lines = []
        skip_keywords = ['relevance', 'view all', 'see views', 'job posting', 
                         'save search', 'clear filters', 'talent network', 
                         '3 months', 'easy or lengthy', 'show all jobs']
        
        for line in lines:
            lower_line = line.lower()
            if any(skip in lower_line for skip in skip_keywords):
                continue
            if len(line) < 2:
                continue
            filtered_lines.append(line)
        
        if not filtered_lines:
            return None
        
        # The title is typically the first substantive line
        title = None
        company = "Unknown Company"
        location = None
        salary = None
        experience = None
        work_type = None
        description_parts = []
        
        for i, line in enumerate(filtered_lines):
            # Skip very short lines or pure numbers
            if len(line) < 3:
                continue
                
            # Detect job title (usually first line, or line that looks like a title)
            if title is None and not any(x in line.lower() for x in ['$', 'yoe', 'remote', 'hybrid', 'onsite', 'full time', 'part time']):
                # Check if it could be a company description (has colon)
                if ':' in line and i > 0:
                    # This might be company: description
                    company = line.split(':')[0].strip()
                    continue
                title = line
                continue
            
            # Detect location (contains state abbreviation or country)
            if location is None:
                location_indicators = ['united states', ', ', 'remote', 'hybrid', 'onsite']
                if any(ind in line.lower() for ind in location_indicators):
                    if 'remote' in line.lower() or 'hybrid' in line.lower() or 'onsite' in line.lower():
                        if len(line) < 50:  # Avoid full descriptions
                            location = line
                            continue
                    elif ', ' in line and len(line) < 100:
                        location = line
                        continue
            
            # Detect salary
            if '$' in line and ('/' in line or 'k' in line.lower() or 'yr' in line.lower()):
                salary = line
                continue
            
            # Detect experience (YOE = Years of Experience)
            if 'yoe' in line.lower() or 'years' in line.lower():
                experience = line
                continue
            
            # Detect work type
            if line.lower() in ['remote', 'hybrid', 'onsite', 'full time', 'part time']:
                work_type = line
                continue
            
            # Detect company (often has colon describing what they do)
            if ':' in line and len(line) < 200:
                potential_company = line.split(':')[0].strip()
                if len(potential_company) > 2 and len(potential_company) < 50:
                    company = potential_company
                continue
        
        # If we still don't have a title, try the link text
        if not title or len(title) < 3:
            # Try to extract title from link text (first line usually)
            link_lines = [l.strip() for l in link_text.split('\n') if l.strip()]
            for ll in link_lines:
                if ll.lower() not in ['view all', 'see views', 'job posting'] and len(ll) > 3:
                    title = ll
                    break
        
        if not title or len(title) < 3:
            return None
        
        # Build description
        if salary:
            description_parts.append(f"Salary: {salary}")
        if experience:
            description_parts.append(f"Experience: {experience}")
        if work_type:
            description_parts.append(f"Work Type: {work_type}")
        
        description = " | ".join(description_parts) if description_parts else None
        
        # Determine tags
        tags = []
        full_text = card_text.lower()
        
        if self._is_new_grad_job(title, full_text):
            tags.append("new-grad")
        
        if "intern" in full_text:
            tags.append("internship")
        
        if "remote" in full_text:
            tags.append("remote")
        
        if "hybrid" in full_text:
            tags.append("hybrid")
        
        return ScrapedJob(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=job_url,
            source_url=self._build_search_url(),
            tags=tags,
        )

    async def _parse_job_card(self, page: Page, link_element) -> Optional[ScrapedJob]:
        """Parse a job card element into a ScrapedJob (legacy method, kept for compatibility)."""
        try:
            # Get the job URL
            href = await link_element.get_attribute("href")
            if not href:
                return None
            
            job_url = urljoin(self.BASE_URL, href)
            
            # Try to get the parent container with job info
            # Navigate up to find the job card container
            parent = link_element
            for _ in range(5):  # Go up at most 5 levels
                parent = await parent.evaluate_handle("el => el.parentElement")
                if not parent:
                    break
            
            # Get text content from the card area
            card_text = await link_element.evaluate("""
                (el) => {
                    // Try to get the container with job info
                    let container = el;
                    for (let i = 0; i < 8 && container; i++) {
                        container = container.parentElement;
                    }
                    return container ? container.innerText : el.innerText;
                }
            """)
            
            # Parse job info from text content
            lines = [line.strip() for line in card_text.split('\n') if line.strip()]
            
            if not lines:
                return None
            
            # Extract job details
            title = lines[0] if lines else "Unknown Title"
            
            # Look for company name (usually after location or in favicon alt)
            company = "Unknown Company"
            location = None
            salary = None
            experience = None
            work_type = None
            
            for i, line in enumerate(lines):
                # Location patterns
                if any(loc in line for loc in ["United States", "Remote", "Hybrid", "Onsite"]):
                    if "United States" in line or ", " in line:
                        location = line
                    elif line in ["Remote", "Hybrid", "Onsite"]:
                        work_type = line
                
                # Salary patterns
                if "$" in line and ("/" in line or "k" in line.lower()):
                    salary = line
                
                # Experience patterns (e.g., "0+ YOE", "5+ YOE")
                if "YOE" in line or "years" in line.lower():
                    experience = line
                
                # Company often follows the title or is marked with a colon
                if ":" in line and i > 0:
                    company = line.split(":")[0].strip()
            
            # If we couldn't find a company, try to extract from URL patterns
            if company == "Unknown Company":
                company = self._extract_company_from_text(lines)
            
            # Build description from available info
            description_parts = []
            if salary:
                description_parts.append(f"Salary: {salary}")
            if experience:
                description_parts.append(f"Experience: {experience}")
            if work_type:
                description_parts.append(f"Work Type: {work_type}")
            
            description = " | ".join(description_parts) if description_parts else None
            
            # Determine tags
            tags = []
            full_text = " ".join(lines).lower()
            
            if self._is_new_grad_job(title, description):
                tags.append("new-grad")
            
            if "intern" in full_text:
                tags.append("internship")
            
            if "remote" in full_text:
                tags.append("remote")
            
            if "hybrid" in full_text:
                tags.append("hybrid")
            
            return ScrapedJob(
                title=title,
                company=company,
                location=location,
                description=description,
                apply_url=job_url,
                source_url=self._build_search_url(),
                tags=tags,
            )
            
        except Exception as e:
            print(f"⚠️ Error extracting job details: {e}")
            return None
    
    def _extract_company_from_text(self, lines: list[str]) -> str:
        """Try to extract company name from job card text."""
        # Common patterns: company name often appears after location
        for i, line in enumerate(lines):
            # Skip title (first line) and common non-company lines
            if i == 0:
                continue
            
            # Skip lines that look like metadata
            if any(skip in line.lower() for skip in [
                "yoe", "remote", "hybrid", "onsite", "full time", "part time",
                "contract", "internship", "$", "view all", "see views"
            ]):
                continue
            
            # If it looks like a company description (ends with period, has colons)
            if ":" in line:
                return line.split(":")[0].strip()
            
            # If it's a short name-like string
            if len(line) < 50 and not any(c.isdigit() for c in line):
                return line
        
        return "Unknown Company"
    
    async def scrape_job_details(self, job_url: str) -> Optional[dict]:
        """Scrape detailed information from a specific job posting page.
        
        Args:
            job_url: URL of the job posting (e.g., https://hiring.cafe/viewjob/xxx)
            
        Returns:
            Dictionary with detailed job information, or None if scraping fails.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            
            try:
                page = await browser.new_page()
                await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)  # Wait for dynamic content
                
                # Extract job details from the page
                details = await page.evaluate("""
                    () => {
                        const getText = (selector) => {
                            const el = document.querySelector(selector);
                            return el ? el.innerText.trim() : null;
                        };
                        
                        return {
                            title: document.querySelector('h1')?.innerText?.trim(),
                            content: document.body.innerText,
                        };
                    }
                """)
                
                return details
                
            except Exception as e:
                print(f"❌ Error scraping job details: {e}")
                return None
            finally:
                await browser.close()


async def scrape_hiring_cafe(
    config: Optional[SearchConfig] = None,
) -> list[ScrapedJob]:
    """Convenience function to scrape hiring.cafe with default settings.
    
    Args:
        config: Optional search configuration. Defaults to new-grad SWE.
        
    Returns:
        List of scraped jobs.
    """
    scraper = HiringCafeScraper(config=config)
    return await scraper.scrape()


def scrape_hiring_cafe_sync(
    config: Optional[SearchConfig] = None,
) -> list[ScrapedJob]:
    """Synchronous wrapper for scraping hiring.cafe.
    
    Args:
        config: Optional search configuration. Defaults to new-grad SWE.
        
    Returns:
        List of scraped jobs.
    """
    return asyncio.run(scrape_hiring_cafe(config))


# Main entry point for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape jobs from hiring.cafe")
    parser.add_argument("--query", "-q", default="software engineer", help="Search query")
    parser.add_argument("--max-results", "-n", type=int, default=20, help="Maximum jobs to scrape")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")
    parser.add_argument("--slow-mo", type=int, default=0, help="Slow down actions (ms)")
    
    args = parser.parse_args()
    
    config = SearchConfig(
        query=args.query,
        max_results=args.max_results,
    )
    
    scraper = HiringCafeScraper(
        config=config,
        headless=not args.no_headless,
        slow_mo=args.slow_mo,
    )
    
    jobs = asyncio.run(scraper.scrape())
    
    print(f"\n{'='*60}")
    print(f"Found {len(jobs)} jobs")
    print('='*60)
    
    for i, job in enumerate(jobs, 1):
        print(f"\n[{i}] {job.title}")
        print(f"    Company:  {job.company}")
        print(f"    Location: {job.location or 'N/A'}")
        print(f"    Tags:     {', '.join(job.tags) if job.tags else 'None'}")
        print(f"    URL:      {job.apply_url}")
