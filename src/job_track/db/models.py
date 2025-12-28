"""Database models for job-track.

This module defines SQLAlchemy models for jobs and profiles.
"""

import datetime
import json
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Job(Base):
    """Model representing a job listing.

    Attributes:
        id: Unique identifier for the job.
        title: Job title.
        company: Company name.
        location: Job location.
        description: Full job description text.
        apply_url: URL to apply for the job on company site.
        source_url: Original URL where job was scraped from.
        scraped_at: Timestamp when job was scraped.
        tags: JSON array of tags (e.g., "new-grad", "remote").
        is_applied: Whether user has applied to this job.
        applied_at: Timestamp when user applied.
        profile_id: ID of profile used when applying.
        resume_version: Version of resume used when applying.
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    scraped_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    is_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    resume_version: Mapped[Optional[int]] = mapped_column(nullable=True)

    def get_tags(self) -> list[str]:
        """Parse tags JSON into a list."""
        if not self.tags:
            return []
        return json.loads(self.tags)

    def set_tags(self, tags: list[str]) -> None:
        """Set tags from a list."""
        self.tags = json.dumps(tags)

    def to_dict(self) -> dict:
        """Convert job to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "apply_url": self.apply_url,
            "source_url": self.source_url,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "tags": self.get_tags(),
            "is_applied": self.is_applied,
            "is_pending": self.is_pending,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "profile_id": self.profile_id,
            "resume_version": self.resume_version,
        }


class Profile(Base):
    """Model representing a user profile for job applications.

    Attributes:
        id: Unique identifier for the profile.
        name: Full name.
        email: Email address.
        phone: Phone number.
        linkedin_url: LinkedIn profile URL.
        github_url: GitHub profile URL.
        portfolio_url: Portfolio/website URL.
        resume_versions: JSON with resume version metadata.
        created_at: Timestamp when profile was created.
        updated_at: Timestamp when profile was last updated.
    """

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    resume_versions: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON array of {version, filename, uploaded_at}
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    def get_resume_versions(self) -> list[dict]:
        """Parse resume versions JSON into a list."""
        if not self.resume_versions:
            return []
        return json.loads(self.resume_versions)

    def add_resume_version(self, filename: str) -> int:
        """Add a new resume version and return the version number."""
        versions = self.get_resume_versions()
        new_version = len(versions) + 1
        versions.append({
            "version": new_version,
            "filename": filename,
            "uploaded_at": datetime.datetime.now().isoformat(),
        })
        self.resume_versions = json.dumps(versions)
        return new_version

    def get_latest_resume_version(self) -> Optional[dict]:
        """Get the latest resume version metadata."""
        versions = self.get_resume_versions()
        if not versions:
            return None
        return versions[-1]

    def to_dict(self) -> dict:
        """Convert profile to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "linkedin_url": self.linkedin_url,
            "github_url": self.github_url,
            "portfolio_url": self.portfolio_url,
            "resume_versions": self.get_resume_versions(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def get_db_path() -> Path:
    """Get the database file path."""
    data_dir = Path.home() / ".local" / "share" / "job-track"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "job_track.db"


def get_resume_dir(profile_id: str) -> Path:
    """Get the resume storage directory for a profile."""
    resume_dir = Path.home() / ".local" / "share" / "job-track" / "resumes" / profile_id
    resume_dir.mkdir(parents=True, exist_ok=True)
    return resume_dir


def get_engine(db_path: Optional[Path] = None):
    """Create database engine."""
    if db_path is None:
        db_path = get_db_path()
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(db_path: Optional[Path] = None):
    """Initialize the database, creating tables if needed."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: Optional[Path] = None):
    """Get a database session."""
    engine = init_db(db_path)
    Session = sessionmaker(bind=engine)
    return Session()
