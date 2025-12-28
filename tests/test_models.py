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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = init_db(db_path)
        session = get_session(db_path)
        yield session
        session.close()
        engine.dispose()


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
        
        # Add resume versions (new format with optional names)
        v1 = profile.add_resume_version("resume_v1.pdf")
        v2 = profile.add_resume_version("resume_v2.pdf", name="Tech Resume")
        temp_db.commit()
        
        # Verify returned version dicts
        assert v1["filename"] == "resume_v1.pdf"
        assert v1["is_named"] is False
        assert v1["name"] == "Resume 1"
        
        assert v2["filename"] == "resume_v2.pdf"
        assert v2["is_named"] is True
        assert v2["name"] == "Tech Resume"
        
        versions = profile.get_resume_versions()
        assert len(versions) == 2
        
        # Find versions by filename (order may change due to sorting)
        filenames = [v["filename"] for v in versions]
        assert "resume_v1.pdf" in filenames
        assert "resume_v2.pdf" in filenames
        
        # Check the named version
        named_versions = profile.get_named_resume_versions()
        assert len(named_versions) == 1
        assert named_versions[0]["name"] == "Tech Resume"

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
        
        # Add some resumes (using new format with optional names)
        profile.add_resume_version("v1.pdf")
        profile.add_resume_version("v2.pdf", name="General")
        profile.add_resume_version("v3.pdf")
        temp_db.commit()
        
        latest = profile.get_latest_resume_version()
        assert latest["name"] == "Resume 3"  # Third unnamed resume
        assert latest["filename"] == "v3.pdf"
        assert latest["is_named"] is False

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

    def test_profile_address_fields(self, temp_db):
        """Test profile address fields."""
        profile = Profile(
            name="Charlie Brown",
            email="charlie@example.com",
            address_street="123 Main St",
            address_city="Springfield",
            address_state="IL",
            address_zip="62701",
            address_country="USA",
        )
        temp_db.add(profile)
        temp_db.commit()
        
        assert profile.address_street == "123 Main St"
        assert profile.address_city == "Springfield"
        assert profile.address_state == "IL"
        assert profile.address_zip == "62701"
        assert profile.address_country == "USA"
        
        # Test get_full_address helper
        full_addr = profile.get_full_address()
        assert "123 Main St" in full_addr
        assert "Springfield" in full_addr
        assert "IL" in full_addr
        assert "62701" in full_addr
        assert "USA" in full_addr

    def test_profile_partial_address(self, temp_db):
        """Test profile with partial address."""
        profile = Profile(
            name="Dan Smith",
            email="dan@example.com",
            address_city="Boston",
            address_state="MA",
        )
        temp_db.add(profile)
        temp_db.commit()
        
        full_addr = profile.get_full_address()
        assert "Boston" in full_addr
        assert "MA" in full_addr
