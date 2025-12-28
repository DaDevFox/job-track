"""Unit tests for scraper parsers."""

from jobtrack import schemas
from jobtrack.scraping.generic import parse_basic_listing
from jobtrack.scraping.lever import parse_lever_listings


def _request(source: str, **overrides) -> schemas.JobScrapeRequest:
    payload = {
        "url": "https://jobs.example.com",
        "company": "ExampleCo",
        "source": source,
        "new_grad_only": False,
        "limit": 10,
    }
    payload.update(overrides)
    return schemas.JobScrapeRequest(**payload)


def test_parse_lever_extracts_jobs():
    html = """
    <div class="posting">
      <a class="posting-title" href="/posting1">
        <h5>New Grad Software Engineer</h5>
      </a>
      <div class="posting-categories">
        <span>Engineering</span>
        <span>New Grad</span>
      </div>
      <span class="sort-by-location">Remote</span>
    </div>
    <div class="posting">
      <a class="posting-title" href="/posting2">
        <h5>Senior Manager</h5>
      </a>
      <div class="posting-categories">
        <span>Leadership</span>
      </div>
      <span class="sort-by-location">NYC</span>
    </div>
    """
    request = _request("lever")
    jobs = parse_lever_listings(html, request)
    assert len(jobs) == 2
    assert jobs[0].title == "New Grad Software Engineer"
    assert jobs[0].new_grad is True
    assert str(jobs[0].apply_url).endswith("/posting1")


def test_parse_basic_listing_applies_new_grad_filter():
    html = """
    <ul>
      <li data-job-id="1">
        <a href="https://example.com/jobs/1">Entry Level Data Scientist</a>
        <div class="description">Entry level opportunity</div>
        <div class="location">Remote</div>
      </li>
      <li data-job-id="2">
        <a href="https://example.com/jobs/2">Principal Architect</a>
        <div class="description">15+ years required</div>
        <div class="location">SF</div>
      </li>
    </ul>
    """
    request = _request("generic", new_grad_only=True)
    jobs = parse_basic_listing(html, request)
    assert len(jobs) == 1
    assert jobs[0].title == "Entry Level Data Scientist"
    assert jobs[0].new_grad is True
