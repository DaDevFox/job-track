"""Pydantic schemas for API IO."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ResumeVersionRead(BaseModel):
    id: UUID
    filename: str
    stored_path: str
    uploaded_at: datetime
    notes: Optional[str]


class ProfileBase(BaseModel):
    label: str
    full_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    autofill_data: dict[str, str] = Field(default_factory=dict)

    @field_validator("autofill_data", mode="before")
    @classmethod
    def default_autofill(cls, value: Optional[dict]) -> dict[str, str]:
        return value or {}


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(BaseModel):
    label: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    autofill_data: Optional[dict[str, str]] = None


class ProfileRead(ProfileBase):
    id: UUID
    resume_versions: list[ResumeVersionRead] = Field(default_factory=list)


class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    apply_url: HttpUrl
    source_url: Optional[HttpUrl] = None
    tags: list[str] = Field(default_factory=list)
    new_grad: bool = False

    @field_validator("tags", mode="before")
    @classmethod
    def ensure_tags(cls, value: Optional[list[str]]) -> list[str]:
        if not value:
            return []
        return value


class JobCreate(JobBase):
    pass


class JobRead(JobBase):
    id: UUID
    scraped_at: datetime
    is_applied: bool
    pending_since: Optional[datetime]
    applied_at: Optional[datetime]
    profile_used_id: Optional[UUID]


class JobAppliedRequest(BaseModel):
    profile_id: Optional[UUID] = None
    mark_applied: bool = True


class JobPendingRequest(BaseModel):
    pending: bool = True


class JobScrapeRequest(BaseModel):
    url: HttpUrl
    company: str
    source: str = "generic"
    new_grad_only: bool = True
    limit: int = 25


class JobProfileSelection(BaseModel):
    apply_url: HttpUrl
    profile_id: UUID


class ScrapePreview(BaseModel):
    title: str
    company: str
    location: Optional[str]
    description: Optional[str]
    apply_url: HttpUrl


class ScrapeResponse(BaseModel):
    jobs: list[ScrapePreview]
    inserted: int


class ScrapedJobRead(BaseModel):
    id: UUID
    title: str
    company: str
    location: Optional[str]
    description: Optional[str]
    apply_url: HttpUrl
    source_url: Optional[str]
    scraped_at: datetime
    tags: list[str]
    new_grad: bool
    applied: bool


class ApplyFromScrapedRequest(BaseModel):
    profile_id: Optional[UUID] = None
    notes: Optional[str] = None

