"""Endpoints that manage scraped job listings."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from .. import crud, schemas
from ..database import get_scraped_session, get_session
from ..scraped_store import (
    get_scraped_job,
    list_scraped_jobs,
    mark_scraped_applied,
    store_scraped_jobs,
)
from ..scraping import run_scraper

router = APIRouter()


@router.get("", response_model=list[schemas.ScrapedJobRead])
def list_scraped(
    *,
    include_applied: bool = False,
    new_grad_only: bool | None = None,
    session: Session = Depends(get_scraped_session),
) -> list[schemas.ScrapedJobRead]:
    rows = list_scraped_jobs(
        session,
        include_applied=include_applied,
        new_grad_only=new_grad_only,
    )
    return [
        schemas.ScrapedJobRead(
            id=row.id,
            title=row.title,
            company=row.company,
            location=row.location,
            description=row.description,
            apply_url=row.apply_url,
            source_url=row.source_url,
            scraped_at=row.scraped_at,
            tags=list(row.tags),
            new_grad=row.new_grad,
            applied=row.applied,
        )
        for row in rows
    ]


@router.post("/refresh", response_model=schemas.ScrapeResponse)
async def refresh_scraped_jobs(
    payload: schemas.JobScrapeRequest,
    clear_existing: bool = True,
    session: Session = Depends(get_scraped_session),
) -> schemas.ScrapeResponse:
    """Run the scraper and persist its results in the scraped catalog."""

    jobs = await run_scraper(payload)
    stored = store_scraped_jobs(session, jobs, clear_existing=clear_existing)
    return schemas.ScrapeResponse(
        jobs=[
            schemas.ScrapePreview(
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                apply_url=job.apply_url,
            )
            for job in jobs
        ],
        inserted=len(stored),
    )


@router.post("/{scraped_id}/apply", response_model=schemas.JobRead)
def apply_scraped_job(
    scraped_id: UUID,
    payload: schemas.ApplyFromScrapedRequest,
    session: Session = Depends(get_session),
    scraped_session: Session = Depends(get_scraped_session),
) -> schemas.JobRead:
    scraped = get_scraped_job(scraped_session, scraped_id)
    if not scraped:
        raise HTTPException(status_code=404, detail="Scraped job not found")

    job_payload = schemas.JobCreate(
        title=scraped.title,
        company=scraped.company,
        location=scraped.location,
        description=scraped.description,
        apply_url=scraped.apply_url,
        source_url=scraped.source_url,
        tags=list(scraped.tags),
        new_grad=scraped.new_grad,
    )
    job = crud.upsert_job(session, job_payload)
    job = crud.mark_job_applied(session, job.id, profile_id=payload.profile_id, mark_applied=True)
    if payload.notes:
        job.notes = payload.notes
        session.add(job)
        session.commit()
        session.refresh(job)

    mark_scraped_applied(scraped_session, scraped_id)
    return job
