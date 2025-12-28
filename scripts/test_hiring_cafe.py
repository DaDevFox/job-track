#!/usr/bin/env python3
"""Test script for the hiring.cafe scraper.

This script allows testing the hiring.cafe scraper with various configurations.

Usage:
    python scripts/test_hiring_cafe.py
    python scripts/test_hiring_cafe.py --query "backend engineer"
    python scripts/test_hiring_cafe.py --max-results 50
    python scripts/test_hiring_cafe.py --no-headless  # Show browser for debugging
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from job_track.scraper import (
    HiringCafeScraper,
    SearchConfig,
    PLAYWRIGHT_AVAILABLE,
)


def print_job(job, index: int) -> None:
    """Print a job in a readable format."""
    print(f"\n  [{index}] {job.title}")
    print(f"      Company:     {job.company}")
    print(f"      Location:    {job.location or 'N/A'}")
    print(f"      Tags:        {', '.join(job.tags) if job.tags else 'None'}")
    if job.description:
        print(f"      Description: {job.description[:100]}...")
    print(f"      Apply URL:   {job.apply_url}")


async def test_new_grad_search() -> None:
    """Test the default new-grad software engineer search."""
    print("\n" + "=" * 70)
    print("🎓 Testing: New-Grad Software Engineer Search")
    print("=" * 70)
    
    config = SearchConfig.new_grad_software_engineer()
    config.max_results = 10  # Limit for testing
    
    scraper = HiringCafeScraper(config=config)
    jobs = await scraper.scrape()
    
    print(f"\n📋 Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print_job(job, i)


async def test_intern_search() -> None:
    """Test the internship search."""
    print("\n" + "=" * 70)
    print("🎯 Testing: Software Engineering Internship Search")
    print("=" * 70)
    
    config = SearchConfig.intern_software_engineer()
    config.max_results = 10  # Limit for testing
    
    scraper = HiringCafeScraper(config=config)
    jobs = await scraper.scrape()
    
    print(f"\n📋 Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print_job(job, i)


async def test_custom_search(
    query: str,
    max_results: int,
    headless: bool,
    slow_mo: int,
) -> None:
    """Test a custom search query."""
    print("\n" + "=" * 70)
    print(f"🔍 Testing: Custom Search - '{query}'")
    print("=" * 70)
    
    config = SearchConfig(
        query=query,
        max_results=max_results,
        # Keep default filters for entry-level/internship
        experience_levels=["entry-level", "internship"],
    )
    
    scraper = HiringCafeScraper(
        config=config,
        headless=headless,
        slow_mo=slow_mo,
    )
    jobs = await scraper.scrape()
    
    print(f"\n📋 Found {len(jobs)} jobs")
    for i, job in enumerate(jobs, 1):
        print_job(job, i)
    
    return jobs


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test the hiring.cafe scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/test_hiring_cafe.py
    python scripts/test_hiring_cafe.py --query "frontend developer"
    python scripts/test_hiring_cafe.py --max-results 50 --no-headless
    python scripts/test_hiring_cafe.py --test-all
        """
    )
    parser.add_argument(
        "--query", "-q",
        default="software engineer",
        help="Search query (default: 'software engineer')"
    )
    parser.add_argument(
        "--max-results", "-n",
        type=int,
        default=20,
        help="Maximum number of jobs to scrape (default: 20)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show the browser window (useful for debugging)"
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=0,
        help="Slow down browser actions by N milliseconds (for debugging)"
    )
    parser.add_argument(
        "--test-all",
        action="store_true",
        help="Run all predefined test searches"
    )
    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="Save scraped jobs to the database"
    )
    
    args = parser.parse_args()
    
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright is not installed.")
        print("   Run: pip install playwright && playwright install chromium")
        sys.exit(1)
    
    print("🚀 Hiring.cafe Scraper Test")
    print("=" * 70)
    
    if args.test_all:
        # Run all predefined tests
        await test_new_grad_search()
        await test_intern_search()
    else:
        # Run custom search
        jobs = await test_custom_search(
            query=args.query,
            max_results=args.max_results,
            headless=not args.no_headless,
            slow_mo=args.slow_mo,
        )
        
        if args.save_to_db and jobs:
            print("\n💾 Saving jobs to database...")
            await save_jobs_to_db(jobs)
    
    print("\n✅ Done!")


async def save_jobs_to_db(jobs: list) -> None:
    """Save scraped jobs to the database."""
    from job_track.db.models import Job, get_session
    
    session = get_session()
    saved_count = 0
    
    try:
        for scraped_job in jobs:
            # Check if job already exists (by URL)
            existing = session.query(Job).filter(
                Job.apply_url == scraped_job.apply_url
            ).first()
            
            if existing:
                print(f"  ⏭️  Skipping duplicate: {scraped_job.title}")
                continue
            
            # Create new job record
            job = Job(
                id=scraped_job.generate_id(),
                title=scraped_job.title,
                company=scraped_job.company,
                location=scraped_job.location,
                description=scraped_job.description,
                apply_url=scraped_job.apply_url,
                source_url=scraped_job.source_url,
            )
            job.set_tags(scraped_job.tags)
            
            session.add(job)
            saved_count += 1
            print(f"  ✅ Saved: {scraped_job.title}")
        
        session.commit()
        print(f"\n💾 Saved {saved_count} new jobs to database")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving to database: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
