"""Job endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from .. import crud, schemas
from ..database import get_session
from ..scraping import run_scraper

router = APIRouter()


@router.get("", response_model=list[schemas.JobRead])
def list_jobs(
    *,
    session: Session = Depends(get_session),
    new_grad_only: Optional[bool] = None,
    only_unapplied: Optional[bool] = None,
) -> list[schemas.JobRead]:
    return crud.list_jobs(session, new_grad_only=new_grad_only, only_unapplied=only_unapplied)


@router.post("", response_model=schemas.JobRead)
def upsert_job(*, session: Session = Depends(get_session), payload: schemas.JobCreate) -> schemas.JobRead:
    return crud.upsert_job(session, payload)


@router.post("/{job_id}/pending", response_model=schemas.JobRead)
def mark_pending(
    job_id: UUID,
    payload: schemas.JobPendingRequest,
    session: Session = Depends(get_session),
) -> schemas.JobRead:
    try:
        return crud.mark_job_pending(session, job_id, payload.pending)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/applied", response_model=schemas.JobRead)
def mark_applied(
    job_id: UUID,
    payload: schemas.JobAppliedRequest,
    session: Session = Depends(get_session),
) -> schemas.JobRead:
    try:
        return crud.mark_job_applied(
            session,
            job_id,
            profile_id=payload.profile_id,
            mark_applied=payload.mark_applied,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scrape", response_model=schemas.ScrapeResponse)
async def scrape_jobs(
    payload: schemas.JobScrapeRequest,
    session: Session = Depends(get_session),
) -> schemas.ScrapeResponse:
    jobs = await run_scraper(payload)
    created = crud.bulk_upsert_jobs(session, jobs)
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
        inserted=len(created),
    )


@router.post("/profile-selection")
def note_profile_selection(
    payload: schemas.JobProfileSelection,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    job = crud.note_profile_selection(session, str(payload.apply_url), payload.profile_id)
    return {"status": "recorded" if job else "pending"}
