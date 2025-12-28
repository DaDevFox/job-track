"""Scraper module for job-track.

This module provides job scraping functionality for various sources:
- Generic web scraping with Playwright and BeautifulSoup
- Specialized hiring.cafe scraper for aggregated job listings
"""

from .scraper import (
    ScrapedJob,
    JobScraper,
    PlaywrightScraper,
    SimpleScraper,
    scrape_jobs_sync,
    PLAYWRIGHT_AVAILABLE,
)

from .hiring_cafe import (
    HiringCafeScraper,
    SearchConfig,
    scrape_hiring_cafe,
    scrape_hiring_cafe_sync,
)

__all__ = [
    # Base scraper classes
    "ScrapedJob",
    "JobScraper",
    "PlaywrightScraper",
    "SimpleScraper",
    "scrape_jobs_sync",
    "PLAYWRIGHT_AVAILABLE",
    # Hiring.cafe scraper
    "HiringCafeScraper",
    "SearchConfig",
    "scrape_hiring_cafe",
    "scrape_hiring_cafe_sync",
]
