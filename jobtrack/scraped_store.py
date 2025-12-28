"""Helpers for managing scraped job listings."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlmodel import Session, delete, select

from . import models, schemas

logger = logging.getLogger(__name__)


def store_scraped_jobs(
    session: Session,
    jobs: Iterable[schemas.JobCreate],
    *,
    clear_existing: bool = True,
) -> list[models.ScrapedJob]:
    """Replace or append scraped jobs with validated payloads."""

    if clear_existing:
        deleted = session.exec(delete(models.ScrapedJob))
        session.commit()
        logger.info("Cleared %s existing scraped rows", deleted.rowcount if deleted else 0)

    existing = {
        row.apply_url for row in session.exec(select(models.ScrapedJob.apply_url))
    }
    stored: list[models.ScrapedJob] = []
    for payload in jobs:
        apply_url = str(payload.apply_url)
        if apply_url in existing:
            logger.debug("Skipping duplicate scraped job %s", apply_url)
            continue
        record = models.ScrapedJob(
            title=payload.title,
            company=payload.company,
            location=payload.location,
            description=payload.description,
            apply_url=apply_url,
            source_url=str(payload.source_url) if payload.source_url else None,
            tags=list(payload.tags),
            new_grad=payload.new_grad,
        )
        session.add(record)
        stored.append(record)
        existing.add(apply_url)
    session.commit()
    for record in stored:
        session.refresh(record)
    logger.info("Stored %s scraped rows (deduped from %s URLs)", len(stored), len(existing))
    return stored


def list_scraped_jobs(
    session: Session,
    *,
    include_applied: bool = False,
    new_grad_only: bool | None = None,
) -> list[models.ScrapedJob]:
    statement = select(models.ScrapedJob).order_by(models.ScrapedJob.scraped_at.desc())
    if new_grad_only:
        statement = statement.where(models.ScrapedJob.new_grad == True)  # noqa: E712
    if not include_applied:
        statement = statement.where(models.ScrapedJob.applied == False)  # noqa: E712
    return list(session.exec(statement))


def get_scraped_job(session: Session, scraped_id: UUID) -> Optional[models.ScrapedJob]:
    return session.get(models.ScrapedJob, scraped_id)


def mark_scraped_applied(session: Session, scraped_id: UUID) -> None:
    job = session.get(models.ScrapedJob, scraped_id)
    if not job:
        return
    job.applied = True
    job.applied_at = datetime.utcnow()
    session.add(job)
    session.commit()


def delete_scraped_job(session: Session, scraped_id: UUID) -> bool:
    job = session.get(models.ScrapedJob, scraped_id)
    if not job:
        return False
    session.delete(job)
    session.commit()
    return True


def clear_scraped_jobs(session: Session) -> int:
    result = session.exec(delete(models.ScrapedJob))
    session.commit()
    logger.info("Cleared scraped catalog via API result=%s", result.rowcount if result else 0)
    return result.rowcount or 0
