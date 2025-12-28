"""Profile endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from .. import crud, schemas
from ..database import get_session
from ..storage import persist_upload

router = APIRouter()


@router.get("", response_model=list[schemas.ProfileRead])
def list_profiles(session: Session = Depends(get_session)) -> list[schemas.ProfileRead]:
    return crud.list_profiles(session)


@router.post("", response_model=schemas.ProfileRead)
def create_profile(payload: schemas.ProfileCreate, session: Session = Depends(get_session)) -> schemas.ProfileRead:
    return crud.ensure_profile(session, payload)


@router.patch("/{profile_id}", response_model=schemas.ProfileRead)
def edit_profile(
    profile_id: UUID,
    payload: schemas.ProfileUpdate,
    session: Session = Depends(get_session),
) -> schemas.ProfileRead:
    try:
        return crud.update_profile(session, profile_id, payload)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{profile_id}/resume", response_model=schemas.ResumeVersionRead)
def upload_resume(
    profile_id: UUID,
    session: Session = Depends(get_session),
    file: UploadFile = File(...),
) -> schemas.ResumeVersionRead:
    destination = persist_upload(profile_id, file)
    resume = crud.attach_resume(
        session,
        profile_id,
        filename=file.filename or destination.name,
        stored_path=str(destination),
    )
    return schemas.ResumeVersionRead(**resume.model_dump())
