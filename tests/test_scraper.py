"""Tests for the job scraper."""
import pytest
from backend.scraper import JobScraper, get_scraper


def test_get_scraper():
    """Test getting a scraper instance."""
    scraper = get_scraper()
    assert isinstance(scraper, JobScraper)


def test_scrape_jobs():
    """Test scraping jobs."""
    scraper = JobScraper()
    jobs = scraper.scrape_jobs(search_term="software engineer", location="remote")
    
    assert len(jobs) > 0
    assert all("title" in job for job in jobs)
    assert all("company" in job for job in jobs)
    assert all("url" in job for job in jobs)


def test_scrape_jobs_with_different_terms():
    """Test scraping with different search terms."""
    scraper = JobScraper()
    
    jobs1 = scraper.scrape_jobs(search_term="data scientist")
    jobs2 = scraper.scrape_jobs(search_term="product manager")
    
    assert len(jobs1) > 0
    assert len(jobs2) > 0
    # Demo implementation returns similar jobs with different titles
    assert any("data scientist" in job["title"].lower() for job in jobs1)


def test_scrape_job_details():
    """Test scraping job details."""
    scraper = JobScraper()
    details = scraper.scrape_job_details("https://example.com/job/1")
    
    assert "description" in details
    assert isinstance(details, dict)


def test_scraper_with_location():
    """Test scraping with location parameter."""
    scraper = JobScraper()
    jobs = scraper.scrape_jobs(search_term="engineer", location="New York")
    
    assert len(jobs) > 0
    # Some jobs should have the location
    assert any("New York" in job.get("location", "") for job in jobs)
