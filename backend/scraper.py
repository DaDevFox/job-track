"""Web scraper for job listings."""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobScraper:
    """Simple job scraper for demonstration purposes."""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def scrape_jobs(self, search_term: str = "software engineer", location: str = "", 
                    source: str = "demo") -> List[Dict]:
        """
        Scrape jobs from various sources.
        
        For now, this returns demo data. In production, you would implement
        actual scraping logic for sites like Indeed, LinkedIn, etc.
        Note: Always check robots.txt and terms of service before scraping.
        """
        logger.info(f"Scraping jobs for: {search_term} in {location}")
        
        # Demo data - replace with actual scraping logic
        demo_jobs = [
            {
                "title": f"Senior {search_term}",
                "company": "Tech Corp",
                "location": location or "Remote",
                "description": "Exciting opportunity for an experienced professional.",
                "url": "https://example.com/job/1",
                "source": source
            },
            {
                "title": f"Junior {search_term}",
                "company": "Startup Inc",
                "location": location or "San Francisco, CA",
                "description": "Great entry-level position with growth potential.",
                "url": "https://example.com/job/2",
                "source": source
            },
            {
                "title": f"{search_term} - Mid Level",
                "company": "Big Company LLC",
                "location": location or "New York, NY",
                "description": "Join our growing team of professionals.",
                "url": "https://example.com/job/3",
                "source": source
            }
        ]
        
        logger.info(f"Found {len(demo_jobs)} jobs")
        return demo_jobs
    
    def scrape_job_details(self, url: str) -> Dict:
        """
        Scrape detailed information about a specific job.
        
        In production, this would fetch and parse the job posting page.
        """
        logger.info(f"Scraping job details from: {url}")
        
        # Demo data
        return {
            "description": "Detailed job description would be scraped here.",
            "requirements": ["Requirement 1", "Requirement 2"],
            "benefits": ["Benefit 1", "Benefit 2"]
        }


def get_scraper() -> JobScraper:
    """Get a job scraper instance."""
    return JobScraper()
