"""Test script for SimplifyJobs GitHub scraper."""

import asyncio
from job_track.scraper import (
    SimplifyJobsScraper,
    SimplifyJobsConfig,
    scrape_simplify_jobs_sync,
)


def main():
    """Test the SimplifyJobs scraper."""
    print("Testing SimplifyJobs GitHub Scraper")
    print("=" * 50)
    
    # Create config for software engineering roles
    config = SimplifyJobsConfig.software_engineering()
    print(f"Config: include_inactive={config.include_inactive}, max_age_days={config.max_age_days}")
    
    # Scrape jobs
    print("\nFetching jobs from GitHub...")
    jobs = scrape_simplify_jobs_sync(config)
    
    print(f"\nFound {len(jobs)} active new-grad software engineering jobs")
    print("-" * 50)
    
    # Show first 10 jobs
    for i, job in enumerate(jobs[:10]):
        print(f"\n{i+1}. {job.company} - {job.title}")
        print(f"   Location: {job.location}")
        print(f"   Tags: {', '.join(job.tags)}")
        if job.apply_url:
            print(f"   Apply: {job.apply_url[:60]}...")
    
    # Show summary by company
    print("\n" + "=" * 50)
    print("Top companies by job count:")
    print("-" * 50)
    
    company_counts = {}
    for job in jobs:
        company_counts[job.company] = company_counts.get(job.company, 0) + 1
    
    sorted_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)
    for company, count in sorted_companies[:10]:
        print(f"  {company}: {count} jobs")
    
    # Show FAANG+ jobs
    faang_jobs = [j for j in jobs if "faang+" in j.tags]
    print(f"\nFAANG+ Jobs: {len(faang_jobs)}")
    for job in faang_jobs[:5]:
        print(f"  - {job.company}: {job.title}")
    
    print("\n" + "=" * 50)
    print("Scraper test completed successfully!")


if __name__ == "__main__":
    main()
