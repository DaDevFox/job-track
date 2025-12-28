"""Tests for the job scraper module."""

import pytest
from bs4 import BeautifulSoup

from job_track.scraper.scraper import (
    JobScraper,
    PlaywrightScraper,
    ScrapedJob,
    SimpleScraper,
)


class TestScrapedJob:
    """Tests for ScrapedJob dataclass."""

    def test_generate_id_consistent(self):
        """Test that ID generation is consistent."""
        job1 = ScrapedJob(
            title="Software Engineer",
            company="TechCorp",
            location="Remote",
            description="Great job",
            apply_url="https://techcorp.com/apply/123",
            source_url="https://techcorp.com/careers",
            tags=["new-grad"],
        )
        job2 = ScrapedJob(
            title="Software Engineer",
            company="TechCorp",
            location="Different location",
            description="Different desc",
            apply_url="https://techcorp.com/apply/123",
            source_url="https://techcorp.com/careers",
            tags=[],
        )
        # Same company, title, apply_url should generate same ID
        assert job1.generate_id() == job2.generate_id()

    def test_generate_id_different(self):
        """Test that different jobs have different IDs."""
        job1 = ScrapedJob(
            title="Software Engineer",
            company="TechCorp",
            location="Remote",
            description="Great job",
            apply_url="https://techcorp.com/apply/123",
            source_url="https://techcorp.com/careers",
            tags=[],
        )
        job2 = ScrapedJob(
            title="Product Manager",
            company="TechCorp",
            location="Remote",
            description="Great job",
            apply_url="https://techcorp.com/apply/456",
            source_url="https://techcorp.com/careers",
            tags=[],
        )
        assert job1.generate_id() != job2.generate_id()


class TestJobScraper:
    """Tests for the base JobScraper class."""

    def test_is_new_grad_job_positive(self):
        """Test new-grad detection with matching keywords."""
        scraper = JobScraper()
        
        assert scraper._is_new_grad_job("Junior Software Engineer")
        assert scraper._is_new_grad_job("Entry Level Developer")
        assert scraper._is_new_grad_job("New Grad Software Engineer")
        assert scraper._is_new_grad_job("Associate Data Scientist")
        assert scraper._is_new_grad_job("Software Engineer - Early Career")

    def test_is_new_grad_job_negative(self):
        """Test new-grad detection with non-matching titles."""
        scraper = JobScraper()
        
        assert not scraper._is_new_grad_job("Senior Software Engineer")
        assert not scraper._is_new_grad_job("Staff Engineer")
        assert not scraper._is_new_grad_job("Engineering Manager")
        assert not scraper._is_new_grad_job("Principal Architect")

    def test_is_new_grad_with_description(self):
        """Test new-grad detection using description."""
        scraper = JobScraper()
        
        # Title doesn't match but description does
        assert scraper._is_new_grad_job(
            "Software Engineer",
            "Looking for new graduates with 0-1 years experience"
        )

    def test_extract_company_from_url(self):
        """Test company name extraction from URLs."""
        scraper = JobScraper()
        
        assert scraper._extract_company_from_url("https://www.google.com/careers") == "Google"
        assert scraper._extract_company_from_url("https://careers.microsoft.com/jobs") == "Microsoft"
        assert scraper._extract_company_from_url("https://jobs.netflix.com/") == "Netflix"
        assert scraper._extract_company_from_url("https://meta.com/careers") == "Meta"

    def test_clean_text(self):
        """Test text cleaning."""
        scraper = JobScraper()
        
        assert scraper._clean_text("  Hello   World  ") == "Hello World"
        assert scraper._clean_text("Line1\n\n\nLine2") == "Line1 Line2"
        assert scraper._clean_text(None) is None
        assert scraper._clean_text("") is None


class TestPlaywrightScraper:
    """Tests for PlaywrightScraper HTML parsing."""

    def test_parse_job_listing_page(self):
        """Test parsing a page with multiple job listings."""
        html = """
        <html>
        <body>
            <div class="job-card">
                <h3 class="title">Software Engineer</h3>
                <span class="location">San Francisco, CA</span>
                <a href="/apply/123">Apply Now</a>
            </div>
            <div class="job-card">
                <h3 class="title">Product Manager</h3>
                <span class="location">New York, NY</span>
                <a href="/apply/456">Apply Now</a>
            </div>
        </body>
        </html>
        """
        
        scraper = PlaywrightScraper()
        jobs = scraper._parse_html(html, "https://example.com/careers")
        
        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer"
        assert jobs[0].location == "San Francisco, CA"
        assert jobs[1].title == "Product Manager"

    def test_parse_single_job_page(self):
        """Test parsing a single job detail page."""
        html = """
        <html>
        <body>
            <h1 class="job-title">Junior Data Scientist</h1>
            <div class="location">Remote</div>
            <div class="description">
                Looking for entry-level data scientists to join our team.
                Requirements: Bachelor's degree, Python skills.
            </div>
            <a class="apply-button" href="/submit-application">Apply</a>
        </body>
        </html>
        """
        
        scraper = PlaywrightScraper()
        jobs = scraper._parse_html(html, "https://example.com/job/123")
        
        assert len(jobs) == 1
        assert jobs[0].title == "Junior Data Scientist"
        assert jobs[0].location == "Remote"
        assert "new-grad" in jobs[0].tags  # Should detect "entry-level"

    def test_filter_new_grad(self):
        """Test new-grad filtering."""
        html = """
        <html>
        <body>
            <div class="job-card">
                <h3 class="title">Junior Software Engineer</h3>
                <a href="/apply/1">Apply</a>
            </div>
            <div class="job-card">
                <h3 class="title">Senior Software Engineer</h3>
                <a href="/apply/2">Apply</a>
            </div>
        </body>
        </html>
        """
        
        # Without filter
        scraper = PlaywrightScraper(filter_new_grad=False)
        jobs = scraper._parse_html(html, "https://example.com/careers")
        assert len(jobs) == 2
        
        # With filter
        scraper = PlaywrightScraper(filter_new_grad=True)
        jobs = scraper._parse_html(html, "https://example.com/careers")
        assert len(jobs) == 1
        assert jobs[0].title == "Junior Software Engineer"


class TestSimpleScraper:
    """Tests for SimpleScraper."""

    def test_scrape_page(self):
        """Test simple scraper parsing."""
        html = """
        <html>
        <body>
            <div class="job-card">
                <h3 class="title">Backend Engineer</h3>
                <span class="location">Austin, TX</span>
                <a href="/careers/apply/789">Apply</a>
            </div>
            <div class="job-card">
                <h3 class="title">Frontend Engineer</h3>
                <span class="location">Remote</span>
                <a href="/careers/apply/790">Apply</a>
            </div>
        </body>
        </html>
        """
        
        scraper = SimpleScraper()
        jobs = scraper.scrape_page("https://example.com/jobs", html)
        
        assert len(jobs) == 2
        assert jobs[0].title == "Backend Engineer"
        assert jobs[0].location == "Austin, TX"
        assert jobs[1].title == "Frontend Engineer"

class TestHiringCafeScraper:
    """Tests for the HiringCafeScraper."""

    def test_search_config_defaults(self):
        """Test default search configuration."""
        from job_track.scraper.hiring_cafe import SearchConfig
        
        config = SearchConfig()
        assert config.query == "software engineer"
        assert config.department == "software-engineering"
        assert "entry-level" in config.experience_levels
        assert "internship" in config.experience_levels
        assert config.location == "United States"
        assert config.max_results == 100

    def test_new_grad_preset(self):
        """Test new-grad search preset."""
        from job_track.scraper.hiring_cafe import SearchConfig
        
        config = SearchConfig.new_grad_software_engineer()
        assert config.query == "software engineer"
        assert "entry-level" in config.experience_levels
        assert config.department == "software-engineering"

    def test_intern_preset(self):
        """Test internship search preset."""
        from job_track.scraper.hiring_cafe import SearchConfig
        
        config = SearchConfig.intern_software_engineer()
        assert "intern" in config.query.lower()
        assert "internship" in config.experience_levels

    def test_scraper_builds_url(self):
        """Test that scraper builds correct search URL."""
        from job_track.scraper.hiring_cafe import HiringCafeScraper, SearchConfig
        
        config = SearchConfig(
            query="python developer",
            department="software-engineering",
            experience_levels=["entry-level"],
        )
        scraper = HiringCafeScraper(config=config)
        url = scraper._build_search_url()
        
        assert "hiring.cafe/search" in url
        assert "python+developer" in url or "python%20developer" in url
        assert "software-engineering" in url
        assert "entry-level" in url

    def test_scraper_is_new_grad_detection(self):
        """Test new-grad job detection."""
        from job_track.scraper.hiring_cafe import HiringCafeScraper
        
        scraper = HiringCafeScraper()
        
        # Should be detected as new-grad
        assert scraper._is_new_grad_job("Junior Software Engineer")
        assert scraper._is_new_grad_job("Entry Level Developer")
        assert scraper._is_new_grad_job("New Grad Software Engineer")
        assert scraper._is_new_grad_job("Associate Engineer")
        
        # Should not be detected as new-grad
        assert not scraper._is_new_grad_job("Senior Software Engineer")
        assert not scraper._is_new_grad_job("Staff Engineer")
        assert not scraper._is_new_grad_job("Principal Developer")