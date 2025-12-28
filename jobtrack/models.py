"""Database models."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON, MetaData
from sqlmodel import Field, Relationship, SQLModel


SCRAPED_METADATA = MetaData()


class ResumeVersion(SQLModel, table=True):
    """Stored resume PDF metadata."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", nullable=False, index=True)
    filename: str
    stored_path: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

    profile: Optional["Profile"] = Relationship(back_populates="resume_versions")


class Profile(SQLModel, table=True):
    """Applicant profile with autofill metadata."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    label: str = Field(index=True)
    full_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    autofill_data: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    resume_versions: list[ResumeVersion] = Relationship(back_populates="profile")


class Job(SQLModel, table=True):
    """Job posting information tracked locally."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    apply_url: str = Field(index=True)
    source_url: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    new_grad: bool = Field(default=False, index=True)
    is_applied: bool = Field(default=False, index=True)
    pending_since: Optional[datetime] = Field(default=None, index=True)
    applied_at: Optional[datetime] = Field(default=None, index=True)
    profile_used_id: Optional[UUID] = Field(default=None, foreign_key="profile.id", index=True)
    notes: Optional[str] = None

    profile_used: Optional[Profile] = Relationship()


class ScrapedJob(SQLModel, table=True):
    """Scraped job listing stored in the temporary catalog."""

    metadata = SCRAPED_METADATA

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    apply_url: str = Field(index=True, nullable=False, unique=True)
    source_url: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    new_grad: bool = Field(default=False, index=True)
    notes: Optional[str] = None
    applied: bool = Field(default=False, index=True)
    applied_at: Optional[datetime] = None
