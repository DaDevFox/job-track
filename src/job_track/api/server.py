"""FastAPI server for job-track local API.

This server runs on localhost only and provides endpoints for:
- Managing job listings
- Managing user profiles
- Triggering scrape operations
- Resume uploads
- Streaming scrape progress via SSE
"""

import asyncio
import datetime
import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from job_track.db.models import Job, Profile, ScraperSource, get_resume_dir, get_session, init_db
from job_track.scraper import simplify_jobs
from job_track.scraper.simplify_jobs import SimplifyJobsScraper, SimplifyJobsConfig
from job_track.scraper.hiring_cafe import HiringCafeScraper, SearchConfig
from job_track.scraper.scraper import (
    ScrapeEventType, ScrapeCompleteEvent, ScrapeJobEvent,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for app startup/shutdown."""
    # Startup
    init_db()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title="Job-Track API",
    description="Local API for job tracking and application management",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow CORS from localhost/browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "chrome-extension://*",
        "moz-extension://*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class JobCreate(BaseModel):
    """Model for creating a new job."""

    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    apply_url: str
    source_url: Optional[str] = None
    tags: list[str] = []


class JobUpdate(BaseModel):
    """Model for updating a job."""

    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    apply_url: Optional[str] = None
    tags: Optional[list[str]] = None
    is_applied: Optional[bool] = None
    is_pending: Optional[bool] = None
    profile_id: Optional[str] = None
    resume_version: Optional[str] = None


class ApplyConfirm(BaseModel):
    """Model for confirming a job application."""

    applied: bool
    profile_id: Optional[str] = None
    resume_version: Optional[str] = None


class ProfileCreate(BaseModel):
    """Model for creating a new profile."""

    profile_name: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    phone_device_type: Optional[str] = None  # e.g., "Mobile", "Home", "Work"
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    address_country: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class ProfileUpdate(BaseModel):
    """Model for updating a profile."""

    profile_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    phone_device_type: Optional[str] = None  # e.g., "Mobile", "Home", "Work"
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    address_country: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class ScrapeRequest(BaseModel):
    """Model for triggering a scrape request."""

    urls: list[str]
    filter_new_grad: bool = False


class HiringCafeScrapeRequest(BaseModel):
    """Model for triggering a hiring.cafe scrape request."""

    query: str = "software engineer"
    department: Optional[str] = "software-engineering"
    experience_levels: list[str] = ["entry-level", "internship"]
    location: str = "United States"
    max_results: int = 50


class SimplifyJobsScrapeRequest(BaseModel):
    """Model for triggering a SimplifyJobs scrape request."""

    categories: list[str] = ["software-engineering"]
    include_inactive: bool = False
    location_filter: Optional[str] = None
    max_age_days: Optional[int] = None


# Job endpoints
@app.get("/api/jobs")
async def list_jobs(
    is_applied: Optional[bool] = Query(None),
    is_pending: Optional[bool] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all jobs with optional filters."""
    session = get_session()
    try:
        query = session.query(Job)

        if is_applied is not None:
            query = query.filter(Job.is_applied == is_applied)
        if is_pending is not None:
            query = query.filter(Job.is_pending == is_pending)
        if tag:
            query = query.filter(Job.tags.contains(f'"{tag}"'))
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Job.title.ilike(search_term))
                | (Job.company.ilike(search_term))
                | (Job.description.ilike(search_term))
            )

        total = query.count()
        jobs = query.order_by(Job.scraped_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "jobs": [job.to_dict() for job in jobs],
        }
    finally:
        session.close()


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific job by ID."""
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.to_dict()
    finally:
        session.close()


@app.post("/api/jobs")
async def create_job(job_data: JobCreate):
    """Create a new job listing."""
    session = get_session()
    try:
        job = Job(
            title=job_data.title,
            company=job_data.company,
            location=job_data.location,
            description=job_data.description,
            apply_url=job_data.apply_url,
            source_url=job_data.source_url,
        )
        job.set_tags(job_data.tags)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.to_dict()
    finally:
        session.close()


@app.patch("/api/jobs/{job_id}")
async def update_job(job_id: str, job_data: JobUpdate):
    """Update a job listing."""
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job_data.title is not None:
            job.title = job_data.title
        if job_data.company is not None:
            job.company = job_data.company
        if job_data.location is not None:
            job.location = job_data.location
        if job_data.description is not None:
            job.description = job_data.description
        if job_data.apply_url is not None:
            job.apply_url = job_data.apply_url
        if job_data.tags is not None:
            job.set_tags(job_data.tags)
        if job_data.is_applied is not None:
            job.is_applied = job_data.is_applied
            if job_data.is_applied:
                job.applied_at = datetime.datetime.now()
                job.is_pending = False
        if job_data.is_pending is not None:
            job.is_pending = job_data.is_pending
        if job_data.profile_id is not None:
            job.profile_id = job_data.profile_id
        if job_data.resume_version is not None:
            job.resume_version = job_data.resume_version

        session.commit()
        session.refresh(job)
        return job.to_dict()
    finally:
        session.close()


@app.post("/api/jobs/{job_id}/mark-pending")
async def mark_job_pending(job_id: str):
    """Mark a job as pending (user clicked apply link)."""
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job.is_pending = True
        session.commit()
        return {"status": "pending", "job_id": job_id}
    finally:
        session.close()


@app.post("/api/jobs/{job_id}/confirm-apply")
async def confirm_apply(job_id: str, data: ApplyConfirm):
    """Confirm whether user applied to a job."""
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job.is_pending = False
        if data.applied:
            job.is_applied = True
            job.applied_at = datetime.datetime.now()
            if data.profile_id:
                job.profile_id = data.profile_id
            if data.resume_version:
                job.resume_version = data.resume_version

        session.commit()
        return job.to_dict()
    finally:
        session.close()


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job listing."""
    session = get_session()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        session.delete(job)
        session.commit()
        return {"status": "deleted", "job_id": job_id}
    finally:
        session.close()


# Profile endpoints
@app.get("/api/profiles")
async def list_profiles():
    """List all profiles."""
    session = get_session()
    try:
        profiles = session.query(Profile).all()
        return {"profiles": [profile.to_dict() for profile in profiles]}
    finally:
        session.close()


@app.get("/api/profiles/{profile_id}")
async def get_profile(profile_id: str):
    """Get a specific profile by ID."""
    session = get_session()
    try:
        profile = session.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile.to_dict()
    finally:
        session.close()


@app.post("/api/profiles")
async def create_profile(profile_data: ProfileCreate):
    """Create a new profile."""
    session = get_session()
    try:
        profile = Profile(
            profile_name=profile_data.profile_name,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            email=profile_data.email,
            phone=profile_data.phone,
            address_street=profile_data.address_street,
            address_city=profile_data.address_city,
            address_state=profile_data.address_state,
            address_zip=profile_data.address_zip,
            address_country=profile_data.address_country,
            linkedin_url=profile_data.linkedin_url,
            github_url=profile_data.github_url,
            portfolio_url=profile_data.portfolio_url,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile.to_dict()
    finally:
        session.close()


@app.patch("/api/profiles/{profile_id}")
async def update_profile(profile_id: str, profile_data: ProfileUpdate):
    """Update a profile."""
    session = get_session()
    try:
        profile = session.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        if profile_data.profile_name is not None:
            profile.profile_name = profile_data.profile_name
        if profile_data.first_name is not None:
            profile.first_name = profile_data.first_name
        if profile_data.last_name is not None:
            profile.last_name = profile_data.last_name
        if profile_data.email is not None:
            profile.email = profile_data.email
        if profile_data.phone is not None:
            profile.phone = profile_data.phone
        if profile_data.address_street is not None:
            profile.address_street = profile_data.address_street
        if profile_data.address_city is not None:
            profile.address_city = profile_data.address_city
        if profile_data.address_state is not None:
            profile.address_state = profile_data.address_state
        if profile_data.address_zip is not None:
            profile.address_zip = profile_data.address_zip
        if profile_data.address_country is not None:
            profile.address_country = profile_data.address_country
        if profile_data.linkedin_url is not None:
            profile.linkedin_url = profile_data.linkedin_url
        if profile_data.github_url is not None:
            profile.github_url = profile_data.github_url
        if profile_data.portfolio_url is not None:
            profile.portfolio_url = profile_data.portfolio_url

        session.commit()
        session.refresh(profile)
        return profile.to_dict()
    finally:
        session.close()


@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """Delete a profile."""
    session = get_session()
    try:
        profile = session.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Also delete resume files
        resume_dir = get_resume_dir(profile_id)
        if resume_dir.exists():
            shutil.rmtree(resume_dir)

        session.delete(profile)
        session.commit()
        return {"status": "deleted", "profile_id": profile_id}
    finally:
        session.close()


@app.post("/api/profiles/{profile_id}/resume")
async def upload_resume(profile_id: str, file: UploadFile):
    """Upload a new resume version for a profile."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    session = get_session()
    try:
        profile = session.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Get next version number
        versions = profile.get_resume_versions()
        new_version = len(versions) + 1

        # Save file
        resume_dir = get_resume_dir(profile_id)
        filename = f"resume_v{new_version}.pdf"
        file_path = resume_dir / filename

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Update profile
        profile.add_resume_version(filename)
        session.commit()
        session.refresh(profile)

        return {
            "status": "uploaded",
            "version": new_version,
            "filename": filename,
            "profile": profile.to_dict(),
        }
    finally:
        session.close()


@app.get("/api/profiles/{profile_id}/resume/{version}")
async def get_resume_path(profile_id: str, version: int):
    """Get the file path for a specific resume version."""
    session = get_session()
    try:
        profile = session.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        versions = profile.get_resume_versions()
        if version < 1 or version > len(versions):
            raise HTTPException(status_code=404, detail="Resume version not found")

        version_data = versions[version - 1]
        resume_dir = get_resume_dir(profile_id)
        file_path = resume_dir / version_data["filename"]

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Resume file not found")

        return {
            "version": version,
            "filename": version_data["filename"],
            "path": str(file_path),
            "uploaded_at": version_data["uploaded_at"],
        }
    finally:
        session.close()


import ipaddress
import socket
from urllib.parse import urlparse as url_parse


def is_safe_url(url: str) -> bool:
    """Check if a URL is safe to fetch (not internal network).

    This prevents SSRF attacks by blocking:
    - Non-HTTP(S) schemes
    - Localhost and loopback addresses
    - Private network ranges
    - Link-local addresses

    Args:
        url: URL to validate.

    Returns:
        True if the URL is safe to fetch.
    """
    try:
        parsed = url_parse(url)

        # Only allow HTTP(S)
        if parsed.scheme not in ("http", "https"):
            return False

        # Get the hostname
        hostname = parsed.hostname
        if not hostname:
            return False

        # Block localhost variations
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        # Try to resolve hostname and check IP address
        try:
            # Resolve to IP address
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)

            # Block private, loopback, and link-local addresses
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False

        except (socket.gaierror, ValueError):
            # If we can't resolve, be cautious but allow
            # This handles cases where DNS might not be available
            pass

        return True
    except Exception:
        return False


# Scrape endpoint
@app.post("/api/scrape")
async def scrape_jobs(request: ScrapeRequest):
    """Trigger a scrape operation for the given URLs.

    This endpoint scrapes job listings from the provided URLs and adds them
    to the database. It uses simple HTTP scraping for speed.
    """
    import httpx

    from job_track.scraper.scraper import SimpleScraper

    scraper = SimpleScraper(filter_new_grad=request.filter_new_grad)
    session = get_session()
    results = {"scraped": 0, "added": 0, "skipped": 0, "errors": []}

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for url in request.urls:
                try:
                    # Validate URL to prevent SSRF
                    if not is_safe_url(url):
                        results["errors"].append({
                            "url": url,
                            "error": "URL not allowed (internal or invalid)",
                        })
                        continue

                    response = await client.get(url)
                    response.raise_for_status()
                    html = response.text

                    jobs = scraper.scrape_page(url, html)
                    results["scraped"] += len(jobs)

                    for scraped_job in jobs:
                        # Check if job already exists
                        existing = session.query(Job).filter(
                            Job.apply_url == scraped_job.apply_url
                        ).first()
                        if existing:
                            results["skipped"] += 1
                            continue

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
                        results["added"] += 1

                except httpx.RequestError as e:
                    results["errors"].append({"url": url, "error": str(e)})
                except Exception as e:
                    results["errors"].append({"url": url, "error": str(e)})

        session.commit()
    finally:
        session.close()

    return results


@app.post("/api/scrape/hiring-cafe")
async def scrape_hiring_cafe(request: HiringCafeScrapeRequest):
    """Scrape job listings from hiring.cafe.

    This endpoint uses the hiring.cafe scraper to find new-grad and
    entry-level software engineering positions. It uses Playwright
    for JavaScript rendering.
    
    Default configuration searches for:
    - Query: "software engineer"
    - Department: software-engineering
    - Experience: entry-level, internship
    - Location: United States
    """
    from job_track.scraper.hiring_cafe import HiringCafeScraper, SearchConfig, PLAYWRIGHT_AVAILABLE

    if not PLAYWRIGHT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Playwright is not installed. Run: pip install playwright && playwright install chromium"
        )

    # Create search config from request
    config = SearchConfig(
        query=request.query,
        department=request.department,
        experience_levels=request.experience_levels,
        location=request.location,
        max_results=request.max_results,
    )

    scraper = HiringCafeScraper(config=config, headless=True)
    session = get_session()
    results = {"scraped": 0, "added": 0, "skipped": 0, "errors": []}

    try:
        # Run the scraper
        scraped_jobs = await scraper.scrape()
        results["scraped"] = len(scraped_jobs)

        # Save to database
        for scraped_job in scraped_jobs:
            try:
                # Check if job already exists
                existing = session.query(Job).filter(
                    Job.apply_url == scraped_job.apply_url
                ).first()
                if existing:
                    results["skipped"] += 1
                    continue

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
                results["added"] += 1

            except Exception as e:
                results["errors"].append({
                    "job": scraped_job.title,
                    "error": str(e),
                })

        session.commit()

    except Exception as e:
        results["errors"].append({"error": str(e)})

    finally:
        session.close()

    return results


@app.get("/api/scrape/hiring-cafe/presets")
async def get_hiring_cafe_presets():
    """Get preset search configurations for hiring.cafe.
    
    Returns predefined search configurations for common use cases:
    - new_grad_swe: New-grad software engineering positions
    - intern_swe: Software engineering internships
    """
    return {
        "presets": {
            "new_grad_swe": {
                "query": "software engineer",
                "department": "software-engineering",
                "experience_levels": ["entry-level", "internship"],
                "location": "United States",
                "max_results": 50,
                "description": "New-grad software engineering positions",
            },
            "intern_swe": {
                "query": "software engineer intern",
                "department": "software-engineering",
                "experience_levels": ["internship"],
                "location": "United States",
                "max_results": 50,
                "description": "Software engineering internships",
            },
            "frontend_new_grad": {
                "query": "frontend developer",
                "department": "software-engineering",
                "experience_levels": ["entry-level", "internship"],
                "location": "United States",
                "max_results": 50,
                "description": "New-grad frontend developer positions",
            },
            "backend_new_grad": {
                "query": "backend engineer",
                "department": "software-engineering",
                "experience_levels": ["entry-level", "internship"],
                "location": "United States",
                "max_results": 50,
                "description": "New-grad backend engineer positions",
            },
        }
    }


@app.post("/api/scrape/simplify-jobs")
async def scrape_simplify_jobs(request: SimplifyJobsScrapeRequest):
    """Scrape job listings from SimplifyJobs GitHub repository.

    This endpoint scrapes the SimplifyJobs New-Grad-Positions GitHub
    repository README for curated new-grad job listings.
    """

    session = get_session()
    results = {"scraped": 0, "added": 0, "skipped": 0, "errors": []}
    jobs = await simplify_jobs.scrape_simplify_jobs(simplify_jobs.SimplifyJobsConfig.software_engineering())
    print ("HIIII")
    results["scraped"] = len(jobs)
    for scraped_job in jobs:
        try:
            # Check if job already exists
            existing = session.query(Job).filter(
                Job.apply_url == scraped_job.apply_url
            ).first()
            if existing:
                results["skipped"] += 1
                continue


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
            session.commit()
            results["added"] += 1

        except Exception as e:
            results["errors"].append({
                "job": scraped_job.title,
                "error": str(e),
            })
        finally:
            session.close()

    return results


@app.get("/api/scrape/sources")
async def get_scrape_sources():
    """Get available scraping sources and their configurations.
    
    Returns the list of implemented scrapers with their metadata.
    """
    return {
        "sources": {
            "hiring_cafe": {
                "name": "Hiring.cafe",
                "description": "Job aggregator with filtering for new-grad and entry-level positions",
                "requires_playwright": True,
                "default_schedule": "manual",
            },
            "simplify_jobs": {
                "name": "SimplifyJobs GitHub",
                "description": "Curated list of new-grad software engineering positions",
                "requires_playwright": False,
                "default_schedule": "manual",
            },
            "custom_url": {
                "name": "Custom URL",
                "description": "Scrape job listings from any URL",
                "requires_playwright": False,
                "default_schedule": "manual",
            },
        }
    }


# ============================================================================
# Scraper Source CRUD Endpoints
# ============================================================================


class ScraperSourceCreate(BaseModel):
    """Model for creating a scraper source."""
    name: str
    source_type: str
    config: dict = {}
    schedule: str = "manual"
    enabled: bool = True


class ScraperSourceUpdate(BaseModel):
    """Model for updating a scraper source."""
    name: Optional[str] = None
    source_type: Optional[str] = None
    config: Optional[dict] = None
    schedule: Optional[str] = None
    enabled: Optional[bool] = None


@app.get("/api/scraper-sources")
async def list_scraper_sources():
    """List all configured scraper sources."""
    session = get_session()
    try:
        sources = session.query(ScraperSource).all()
        return {"sources": [s.to_dict() for s in sources]}
    finally:
        session.close()


@app.get("/api/scraper-sources/{source_id}")
async def get_scraper_source(source_id: str):
    """Get a specific scraper source."""
    session = get_session()
    try:
        source = session.query(ScraperSource).filter(ScraperSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Scraper source not found")
        return source.to_dict()
    finally:
        session.close()


@app.post("/api/scraper-sources")
async def create_scraper_source(data: ScraperSourceCreate):
    """Create a new scraper source."""
    session = get_session()
    try:
        source = ScraperSource(
            name=data.name,
            source_type=data.source_type,
            schedule=data.schedule,
            enabled=data.enabled,
        )
        source.set_config(data.config)
        session.add(source)
        session.commit()
        session.refresh(source)
        return source.to_dict()
    finally:
        session.close()


@app.patch("/api/scraper-sources/{source_id}")
async def update_scraper_source(source_id: str, data: ScraperSourceUpdate):
    """Update a scraper source."""
    session = get_session()
    try:
        source = session.query(ScraperSource).filter(ScraperSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Scraper source not found")
        
        if data.name is not None:
            source.name = data.name
        if data.source_type is not None:
            source.source_type = data.source_type
        if data.config is not None:
            source.set_config(data.config)
        if data.schedule is not None:
            source.schedule = data.schedule
        if data.enabled is not None:
            source.enabled = data.enabled
        
        session.commit()
        session.refresh(source)
        return source.to_dict()
    finally:
        session.close()


@app.delete("/api/scraper-sources/{source_id}")
async def delete_scraper_source(source_id: str):
    """Delete a scraper source."""
    session = get_session()
    try:
        source = session.query(ScraperSource).filter(ScraperSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Scraper source not found")
        
        session.delete(source)
        session.commit()
        return {"status": "deleted", "source_id": source_id}
    finally:
        session.close()


# ============================================================================
# Streaming Scrape Endpoints (SSE)
# ============================================================================


async def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@app.get("/api/scrape/stream/{source_id}")
async def scrape_source_stream(source_id: str):
    """Stream scraping progress for a source using Server-Sent Events.
    
    Events emitted:
    - start: {source_id, source_name, source_type}
    - progress: {step, total_steps, message, jobs_found, jobs_added}
    - job: {title, company, location} (for each job found)
    - complete: {total_scraped, total_added, total_skipped, errors}
    - error: {message}
    """
    session = get_session()
    try:
        source = session.query(ScraperSource).filter(ScraperSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Scraper source not found")
        
        source_data = source.to_dict()
    finally:
        session.close()
    
    async def generate_events() -> AsyncGenerator[str, None]:
        """Generate SSE events for scraping progress."""
        config = source_data["config"]
        source_type = source_data["source_type"]
        
        # Create the appropriate scraper based on source type
        scraper = None
        if source_type == "simplify_jobs":
            scraper_config = SimplifyJobsConfig(
                include_inactive=config.get("include_inactive", False),
                categories=config.get("categories", ["software-engineering"]),
                max_age_days=config.get("max_age_days"),
            )
            scraper = SimplifyJobsScraper(scraper_config)
        elif source_type == "hiring_cafe":
            # Parse experience_levels from comma-separated string if needed
            experience_levels = config.get("experience_levels", ["entry-level", "internship"])
            if isinstance(experience_levels, str):
                experience_levels = [e.strip() for e in experience_levels.split(",")]
            
            scraper_config = SearchConfig(
                query=config.get("query", "software engineer"),
                department=config.get("department", "software-engineering"),
                experience_levels=experience_levels,
                location=config.get("location", "United States"),
                max_results=config.get("max_results", 50),
            )
            scraper = HiringCafeScraper(scraper_config)
        else:
            yield await _sse_event("error", {"message": f"Unknown source type: {source_type}"})
            return
        
        # Use the scraper's streaming method
        results = {"scraped": 0, "added": 0, "skipped": 0, "errors": []}
        all_jobs = []
        
        try:
            async for event in scraper.scrape_stream():
                event_dict = event.to_dict()
                event_type = event_dict.pop("event_type")
                
                # Add source_id to start event
                if event_type == "start":
                    event_dict["source_id"] = source_data["id"]
                    event_dict["source_name"] = source_data["name"]
                
                yield await _sse_event(event_type, event_dict)
                
                # Track jobs for database insertion
                if isinstance(event, ScrapeJobEvent):
                    all_jobs.append(event.job)
                
                # When complete, save jobs to database
                if isinstance(event, ScrapeCompleteEvent):
                    results["scraped"] = event.total_scraped
                    results["errors"] = event.errors
                    
                    # Save jobs to database
                    db_session = get_session()
                    try:
                        for job in all_jobs:
                            if not job.apply_url:
                                continue
                            existing = db_session.query(Job).filter(
                                Job.apply_url == job.apply_url
                            ).first()
                            if existing:
                                results["skipped"] += 1
                                continue
                            
                            db_job = Job(
                                title=job.title,
                                company=job.company,
                                location=job.location,
                                description=job.description or f"From {source_type}",
                                apply_url=job.apply_url,
                                source_url=job.source_url,
                            )
                            db_job.set_tags(job.tags)
                            db_session.add(db_job)
                            results["added"] += 1
                        
                        db_session.commit()
                        
                        # Update last scraped time
                        src = db_session.query(ScraperSource).filter(ScraperSource.id == source_id).first()
                        if src:
                            src.last_scraped_at = datetime.datetime.now()
                            db_session.commit()
                    finally:
                        db_session.close()
                    
                    # Send final complete event with database stats
                    yield await _sse_event("complete", {
                        "total_scraped": results["scraped"],
                        "total_added": results["added"],
                        "total_skipped": results["skipped"],
                        "errors": results["errors"],
                    })
                    return
            
        except Exception as e:
            yield await _sse_event("error", {"message": str(e)})
    
    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


def run():
    """Run the API server."""
    uvicorn.run(
        "job_track.api.server:app",
        host="127.0.0.1",
        port=8787,
        reload=False,
    )


if __name__ == "__main__":
    run()
