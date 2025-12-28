"""Database CRUD helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlmodel import Session, select

from . import models, schemas


def upsert_job(session: Session, payload: schemas.JobCreate) -> models.Job:
    """Insert a job if it does not exist, otherwise update metadata."""
    statement = select(models.Job).where(models.Job.apply_url == str(payload.apply_url))
    job = session.exec(statement).first()
    if job:
        for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
            setattr(job, field, value)
        job.scraped_at = datetime.utcnow()
    else:
        job = models.Job(**payload.model_dump(mode="json"))
        session.add(job)
    session.commit()
    session.refresh(job)
    return job


def bulk_upsert_jobs(session: Session, jobs: Iterable[schemas.JobCreate]) -> list[models.Job]:
    results: list[models.Job] = []
    for payload in jobs:
        results.append(upsert_job(session, payload))
    return results


def list_jobs(
    session: Session,
    *,
    new_grad_only: bool | None = None,
    only_unapplied: bool | None = None,
) -> list[models.Job]:
    statement = select(models.Job).order_by(models.Job.scraped_at.desc())
    if new_grad_only:
        statement = statement.where(models.Job.new_grad == True)  # noqa: E712
    if only_unapplied:
        statement = statement.where(models.Job.is_applied == False)  # noqa: E712
    return list(session.exec(statement))


def mark_job_pending(session: Session, job_id: UUID, pending: bool) -> models.Job:
    job = session.get(models.Job, job_id)
    if not job:
        raise ValueError("Job not found")
    job.pending_since = datetime.utcnow() if pending else None
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def mark_job_applied(
    session: Session,
    job_id: UUID,
    *,
    profile_id: Optional[UUID],
    mark_applied: bool = True,
) -> models.Job:
    job = session.get(models.Job, job_id)
    if not job:
        raise ValueError("Job not found")
    job.is_applied = mark_applied
    job.applied_at = datetime.utcnow() if mark_applied else None
    job.profile_used_id = profile_id
    job.pending_since = None
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def ensure_profile(session: Session, payload: schemas.ProfileCreate) -> models.Profile:
    statement = select(models.Profile).where(models.Profile.label == payload.label)
    profile = session.exec(statement).first()
    if profile:
        return profile
    profile = models.Profile(**payload.model_dump())
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(session: Session, profile_id: UUID, payload: schemas.ProfileUpdate) -> models.Profile:
    profile = session.get(models.Profile, profile_id)
    if not profile:
        raise ValueError("Profile not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def list_profiles(session: Session) -> list[models.Profile]:
    statement = select(models.Profile).order_by(models.Profile.label.asc())
    return list(session.exec(statement))


def attach_resume(
    session: Session,
    profile_id: UUID,
    filename: str,
    stored_path: str,
    notes: Optional[str] = None,
) -> models.ResumeVersion:
    profile = session.get(models.Profile, profile_id)
    if not profile:
        raise ValueError("Profile not found")
    resume = models.ResumeVersion(
        profile_id=profile_id,
        filename=filename,
        stored_path=stored_path,
        notes=notes,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


def note_profile_selection(session: Session, apply_url: str, profile_id: UUID) -> Optional[models.Job]:
    statement = select(models.Job).where(models.Job.apply_url == apply_url)
    job = session.exec(statement).first()
    if job:
        job.profile_used_id = profile_id
        session.add(job)
        session.commit()
        session.refresh(job)
    return job
