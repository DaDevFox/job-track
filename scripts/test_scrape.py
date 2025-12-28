#!/usr/bin/env python3
"""Prototype script for testing web scraping functionality.

This script allows testing the scraper without the full application.
Run it with URLs to scrape and validate the output.

Usage:
    python scripts/test_scrape.py https://example.com/careers
    python scripts/test_scrape.py --new-grad https://example.com/careers
    python scripts/test_scrape.py --simple https://example.com/careers  # HTTP only, no JS
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_simple_scrape(url: str, filter_new_grad: bool = False) -> None:
    """Test simple HTTP scraping (no JavaScript rendering).

    Args:
        url: URL to scrape.
        filter_new_grad: Whether to filter for new-grad positions.
    """
    import httpx

    from job_track.scraper.scraper import SimpleScraper

    print(f"\n🔍 Simple scraping: {url}")
    print("-" * 60)

    try:
        # Fetch HTML
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        html = response.text

        # Parse
        scraper = SimpleScraper(filter_new_grad=filter_new_grad)
        jobs = scraper.scrape_page(url, html)

        print_jobs(jobs)

    except httpx.RequestError as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_playwright_scrape(url: str, filter_new_grad: bool = False) -> None:
    """Test Playwright-based scraping (with JavaScript rendering).

    Args:
        url: URL to scrape.
        filter_new_grad: Whether to filter for new-grad positions.
    """
    from job_track.scraper.scraper import PlaywrightScraper, PLAYWRIGHT_AVAILABLE

    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    print(f"\n🎭 Playwright scraping: {url}")
    print("-" * 60)

    try:
        scraper = PlaywrightScraper(filter_new_grad=filter_new_grad)
        jobs = await scraper.scrape_page(url)
        print_jobs(jobs)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def print_jobs(jobs: list) -> None:
    """Print scraped jobs in a readable format.

    Args:
        jobs: List of ScrapedJob objects.
    """
    if not jobs:
        print("📭 No jobs found")
        return

    print(f"📋 Found {len(jobs)} job(s):\n")

    for i, job in enumerate(jobs, 1):
        print(f"  [{i}] {job.title}")
        print(f"      Company: {job.company}")
        if job.location:
            print(f"      Location: {job.location}")
        if job.tags:
            print(f"      Tags: {', '.join(job.tags)}")
        print(f"      Apply URL: {job.apply_url}")
        if job.description:
            desc = job.description[:200] + "..." if len(job.description) > 200 else job.description
            print(f"      Description: {desc}")
        print()


def test_html_parsing() -> None:
    """Test HTML parsing with sample HTML."""
    from job_track.scraper.scraper import PlaywrightScraper

    print("\n🧪 Testing HTML parsing with sample data")
    print("-" * 60)

    # Sample job listing HTML
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Careers - TechCorp</title></head>
    <body>
        <div class="jobs-container">
            <div class="job-card">
                <h3 class="job-title">Junior Software Engineer</h3>
                <div class="job-location">San Francisco, CA</div>
                <p class="job-description">
                    We're looking for new graduates to join our engineering team.
                    Entry level position with great growth opportunities.
                </p>
                <a href="/apply/swe-junior-123" class="apply-button">Apply Now</a>
            </div>
            <div class="job-card">
                <h3 class="job-title">Senior Backend Engineer</h3>
                <div class="job-location">Remote</div>
                <p class="job-description">
                    5+ years experience required. Lead our backend infrastructure.
                </p>
                <a href="/apply/sbe-senior-456" class="apply-button">Apply Now</a>
            </div>
            <div class="job-card">
                <h3 class="job-title">Associate Data Scientist</h3>
                <div class="job-location">New York, NY</div>
                <p class="job-description">
                    Perfect for recent graduates with ML/AI background.
                </p>
                <a href="/apply/ds-associate-789" class="apply-button">Apply Now</a>
            </div>
        </div>
    </body>
    </html>
    """

    scraper = PlaywrightScraper(filter_new_grad=False)
    jobs = scraper._parse_html(sample_html, "https://techcorp.example.com/careers")

    print("All jobs:")
    print_jobs(jobs)

    # Test with new-grad filter
    scraper_filtered = PlaywrightScraper(filter_new_grad=True)
    jobs_filtered = scraper_filtered._parse_html(sample_html, "https://techcorp.example.com/careers")

    print("\nNew-grad filtered jobs:")
    print_jobs(jobs_filtered)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test job scraping functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test with sample HTML (no network required)
    python scripts/test_scrape.py --test

    # Simple HTTP scrape
    python scripts/test_scrape.py --simple https://example.com/careers

    # Playwright scrape (renders JavaScript)
    python scripts/test_scrape.py https://example.com/careers

    # Filter for new-grad positions only
    python scripts/test_scrape.py --new-grad https://example.com/careers
        """
    )

    parser.add_argument(
        "urls",
        nargs="*",
        help="URLs to scrape"
    )
    parser.add_argument(
        "--new-grad",
        action="store_true",
        help="Filter for new-grad positions only"
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Use simple HTTP scraping instead of Playwright"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run with sample HTML to test parsing logic"
    )

    args = parser.parse_args()

    if args.test:
        test_html_parsing()
        return

    if not args.urls:
        parser.print_help()
        print("\n❌ Error: Provide URLs to scrape or use --test flag")
        sys.exit(1)

    for url in args.urls:
        if args.simple:
            test_simple_scrape(url, filter_new_grad=args.new_grad)
        else:
            asyncio.run(test_playwright_scrape(url, filter_new_grad=args.new_grad))


if __name__ == "__main__":
    main()
