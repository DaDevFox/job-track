"""FastAPI server for job-track local API.

This server runs on localhost only and provides endpoints for:
- Managing job listings
- Managing user profiles
- Triggering scrape operations
- Resume uploads
"""

import datetime
import shutil
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from job_track.db.models import Job, Profile, get_resume_dir, get_session, init_db

app = FastAPI(
    title="Job-Track API",
    description="Local API for job tracking and application management",
    version="0.1.0",
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
    resume_version: Optional[int] = None


class ApplyConfirm(BaseModel):
    """Model for confirming a job application."""

    applied: bool
    profile_id: Optional[str] = None
    resume_version: Optional[int] = None


class ProfileCreate(BaseModel):
    """Model for creating a new profile."""

    name: str
    email: str
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class ProfileUpdate(BaseModel):
    """Model for updating a profile."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class ScrapeRequest(BaseModel):
    """Model for triggering a scrape request."""

    urls: list[str]
    filter_new_grad: bool = False


# Initialize DB on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


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
            name=profile_data.name,
            email=profile_data.email,
            phone=profile_data.phone,
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

        if profile_data.name is not None:
            profile.name = profile_data.name
        if profile_data.email is not None:
            profile.email = profile_data.email
        if profile_data.phone is not None:
            profile.phone = profile_data.phone
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
