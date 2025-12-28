"""Database models for job-track.

This module defines SQLAlchemy models for jobs and profiles.
"""

import datetime
import json
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, func
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
        posted_at: Timestamp when job was posted (if available).
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
    posted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
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
    resume_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Version name or ID

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
        address_street: Street address.
        address_city: City.
        address_state: State/Province.
        address_zip: ZIP/Postal code.
        address_country: Country.
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
    address_street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address_zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    resume_versions: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON array of {id, name, filename, uploaded_at, is_named}
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

    def add_resume_version(self, filename: str, name: Optional[str] = None) -> dict:
        """Add a new resume version and return the version info.
        
        Args:
            filename: The filename of the resume.
            name: Optional name for the revision. If provided, this is a named revision.
            
        Returns:
            The new version metadata dict.
        """
        versions = self.get_resume_versions()
        version_id = str(uuid.uuid4())[:8]
        is_named = name is not None
        
        new_version = {
            "id": version_id,
            "name": name if name else f"Resume {len(versions) + 1}",
            "filename": filename,
            "uploaded_at": datetime.datetime.now().isoformat(),
            "is_named": is_named,
        }
        versions.append(new_version)
        
        # Keep named versions + 5 most recent unnamed versions
        named_versions = [v for v in versions if v.get("is_named", False)]
        unnamed_versions = [v for v in versions if not v.get("is_named", False)]
        
        # Keep only the 5 most recent unnamed versions
        if len(unnamed_versions) > 5:
            unnamed_versions = unnamed_versions[-5:]
        
        # Combine and sort by upload time
        all_versions = named_versions + unnamed_versions
        all_versions.sort(key=lambda x: x.get("uploaded_at", ""))
        
        self.resume_versions = json.dumps(all_versions)
        return new_version

    def get_latest_resume_version(self) -> Optional[dict]:
        """Get the latest resume version metadata."""
        versions = self.get_resume_versions()
        if not versions:
            return None
        return versions[-1]
    
    def get_named_resume_versions(self) -> list[dict]:
        """Get all named resume versions."""
        versions = self.get_resume_versions()
        return [v for v in versions if v.get("is_named", False)]
    
    def get_full_address(self) -> str:
        """Get the full address as a formatted string."""
        parts = []
        if self.address_street:
            parts.append(self.address_street)
        city_state = ", ".join(filter(None, [self.address_city, self.address_state]))
        if city_state:
            parts.append(city_state)
        if self.address_zip:
            parts.append(self.address_zip)
        if self.address_country:
            parts.append(self.address_country)
        return ", ".join(parts) if parts else ""

    def to_dict(self) -> dict:
        """Convert profile to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "address_street": self.address_street,
            "address_city": self.address_city,
            "address_state": self.address_state,
            "address_zip": self.address_zip,
            "address_country": self.address_country,
            "full_address": self.get_full_address(),
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


def _migrate_db(engine):
    """Run any needed database migrations."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    
    # Check if profiles table needs address columns
    if "profiles" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("profiles")]
        new_columns = [
            ("address_street", "VARCHAR(255)"),
            ("address_city", "VARCHAR(100)"),
            ("address_state", "VARCHAR(100)"),
            ("address_zip", "VARCHAR(20)"),
            ("address_country", "VARCHAR(100)"),
        ]
        with engine.connect() as conn:
            for col_name, col_type in new_columns:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE profiles ADD COLUMN {col_name} {col_type}"))
            conn.commit()
    
    # Check if jobs table needs posted_at column
    if "jobs" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("jobs")]
        with engine.connect() as conn:
            if "posted_at" not in columns:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN posted_at DATETIME"))
            # Also handle resume_version type change (was int, now string)
            conn.commit()


def init_db(db_path: Optional[Path] = None):
    """Initialize the database, creating tables if needed."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    _migrate_db(engine)
    return engine


def get_session(db_path: Optional[Path] = None):
    """Get a database session."""
    engine = init_db(db_path)
    Session = sessionmaker(bind=engine)
    return Session()
