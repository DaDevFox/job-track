"""Test the streaming scrapers."""

import asyncio
from job_track.scraper.simplify_jobs import SimplifyJobsScraper, SimplifyJobsConfig


async def test_simplify_stream():
    """Test SimplifyJobs streaming scraper."""
    config = SimplifyJobsConfig(categories=['software-engineering'], max_age_days=30)
    scraper = SimplifyJobsScraper(config)
    job_count = 0
    
    async for event in scraper.scrape_stream():
        event_dict = event.to_dict()
        event_type = event_dict['event_type']
        
        if event_type == 'start':
            print(f"Started: {event_dict['source_name']}")
        elif event_type == 'progress':
            print(f"Progress: {event_dict['message']}")
        elif event_type == 'job':
            job_count += 1
            if job_count <= 5:  # Print first 5 jobs
                print(f"  Job: {event_dict['title']} at {event_dict['company']}")
            elif job_count == 6:
                print("  ...")
        elif event_type == 'complete':
            print(f"Complete: {event_dict['total_scraped']} jobs found")
        elif event_type == 'error':
            print(f"Error: {event_dict['message']}")
    
    print(f"\nTotal job events: {job_count}")


if __name__ == "__main__":
    asyncio.run(test_simplify_stream())
