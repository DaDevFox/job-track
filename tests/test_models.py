"""Tests for database models."""

import json
import tempfile
from pathlib import Path

import pytest

from job_track.db.models import (
    Job,
    Profile,
    get_session,
    init_db,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = init_db(db_path)
        session = get_session(db_path)
        yield session
        session.close()


class TestJobModel:
    """Tests for the Job model."""

    def test_create_job(self, temp_db):
        """Test creating a new job."""
        job = Job(
            title="Software Engineer",
            company="TechCorp",
            location="San Francisco",
            description="Great opportunity",
            apply_url="https://techcorp.com/apply",
        )
        temp_db.add(job)
        temp_db.commit()
        
        assert job.id is not None
        assert job.is_applied is False
        assert job.scraped_at is not None

    def test_job_tags(self, temp_db):
        """Test job tags functionality."""
        job = Job(
            title="Junior Engineer",
            company="StartupCo",
            apply_url="https://startup.co/apply",
        )
        job.set_tags(["new-grad", "remote"])
        temp_db.add(job)
        temp_db.commit()
        
        tags = job.get_tags()
        assert "new-grad" in tags
        assert "remote" in tags

    def test_job_to_dict(self, temp_db):
        """Test job serialization."""
        job = Job(
            title="Data Scientist",
            company="DataCorp",
            location="Remote",
            apply_url="https://datacorp.com/apply",
        )
        job.set_tags(["ml", "python"])
        temp_db.add(job)
        temp_db.commit()
        
        data = job.to_dict()
        assert data["title"] == "Data Scientist"
        assert data["company"] == "DataCorp"
        assert "ml" in data["tags"]
        assert data["is_applied"] is False


class TestProfileModel:
    """Tests for the Profile model."""

    def test_create_profile(self, temp_db):
        """Test creating a new profile."""
        profile = Profile(
            name="John Doe",
            email="john@example.com",
            phone="+1-555-555-5555",
        )
        temp_db.add(profile)
        temp_db.commit()
        
        assert profile.id is not None
        assert profile.created_at is not None

    def test_profile_resume_versions(self, temp_db):
        """Test resume versioning."""
        profile = Profile(
            name="Jane Smith",
            email="jane@example.com",
        )
        temp_db.add(profile)
        temp_db.commit()
        
        # Add resume versions
        v1 = profile.add_resume_version("resume_v1.pdf")
        v2 = profile.add_resume_version("resume_v2.pdf")
        temp_db.commit()
        
        assert v1 == 1
        assert v2 == 2
        
        versions = profile.get_resume_versions()
        assert len(versions) == 2
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2

    def test_profile_latest_resume(self, temp_db):
        """Test getting latest resume."""
        profile = Profile(
            name="Bob Builder",
            email="bob@example.com",
        )
        temp_db.add(profile)
        temp_db.commit()
        
        # No resumes yet
        assert profile.get_latest_resume_version() is None
        
        # Add some resumes
        profile.add_resume_version("v1.pdf")
        profile.add_resume_version("v2.pdf")
        profile.add_resume_version("v3.pdf")
        temp_db.commit()
        
        latest = profile.get_latest_resume_version()
        assert latest["version"] == 3
        assert latest["filename"] == "v3.pdf"

    def test_profile_to_dict(self, temp_db):
        """Test profile serialization."""
        profile = Profile(
            name="Alice Wonder",
            email="alice@example.com",
            linkedin_url="https://linkedin.com/in/alice",
        )
        profile.add_resume_version("alice_resume.pdf")
        temp_db.add(profile)
        temp_db.commit()
        
        data = profile.to_dict()
        assert data["name"] == "Alice Wonder"
        assert data["email"] == "alice@example.com"
        assert data["linkedin_url"] == "https://linkedin.com/in/alice"
        assert len(data["resume_versions"]) == 1
