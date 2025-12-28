"""FastAPI application for job tracking."""
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from contextlib import asynccontextmanager
import logging

from backend.models import init_db, get_db, Job as JobModel, Application as ApplicationModel
from backend.schemas import (
    Job, JobCreate, 
    Application, ApplicationCreate, ApplicationUpdate
)
from backend.scraper import get_scraper, JobScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")
    yield
    # Cleanup code would go here if needed


app = FastAPI(title="Job Track API", version="1.0.0", lifespan=lifespan)


@app.get("/")
def read_root():
    """Root endpoint."""
    return {
        "message": "Job Track API",
        "version": "1.0.0",
        "endpoints": {
            "jobs": "/jobs",
            "applications": "/applications",
            "scrape": "/scrape"
        }
    }


# Job endpoints
@app.get("/jobs", response_model=List[Job])
def get_jobs(
    skip: int = 0,
    limit: int = 100,
    company: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all jobs."""
    query = db.query(JobModel)
    if company:
        query = query.filter(JobModel.company.contains(company))
    jobs = query.offset(skip).limit(limit).all()
    return jobs


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job."""
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs", response_model=Job)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    """Create a new job."""
    db_job = JobModel(**job.model_dump())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """Delete a job."""
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}


# Application endpoints
@app.get("/applications", response_model=List[Application])
def get_applications(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all applications."""
    query = db.query(ApplicationModel)
    if status:
        query = query.filter(ApplicationModel.status == status)
    applications = query.offset(skip).limit(limit).all()
    return applications


@app.get("/applications/{application_id}", response_model=Application)
def get_application(application_id: int, db: Session = Depends(get_db)):
    """Get a specific application."""
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@app.post("/applications", response_model=Application)
def create_application(application: ApplicationCreate, db: Session = Depends(get_db)):
    """Create a new application."""
    db_application = ApplicationModel(**application.model_dump())
    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    return db_application


@app.patch("/applications/{application_id}", response_model=Application)
def update_application(
    application_id: int,
    application: ApplicationUpdate,
    db: Session = Depends(get_db)
):
    """Update an application."""
    db_application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()
    if not db_application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    update_data = application.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_application, field, value)
    
    db.commit()
    db.refresh(db_application)
    return db_application


@app.delete("/applications/{application_id}")
def delete_application(application_id: int, db: Session = Depends(get_db)):
    """Delete an application."""
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(application)
    db.commit()
    return {"message": "Application deleted successfully"}


# Scraping endpoints
@app.post("/scrape")
def scrape_jobs(
    search_term: str = Query(default="software engineer"),
    location: str = Query(default=""),
    db: Session = Depends(get_db),
    scraper: JobScraper = Depends(get_scraper)
):
    """Scrape jobs and save to database."""
    logger.info(f"Scraping jobs: {search_term} in {location}")
    
    jobs = scraper.scrape_jobs(search_term=search_term, location=location)
    
    created_jobs = []
    for job_data in jobs:
        # Check if job already exists (by URL)
        existing = db.query(JobModel).filter(JobModel.url == job_data["url"]).first()
        if existing:
            logger.info(f"Job already exists: {job_data['title']}")
            continue
        
        db_job = JobModel(**job_data)
        db.add(db_job)
        created_jobs.append(job_data)
    
    db.commit()
    
    return {
        "message": f"Scraped {len(jobs)} jobs, created {len(created_jobs)} new entries",
        "jobs_created": len(created_jobs),
        "jobs_found": len(jobs)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


def main():
    """Entry point for running the API server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
