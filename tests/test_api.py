"""Tests for the API server."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from job_track.db.models import init_db


@pytest.fixture
def test_client():
    """Create a test client with a temporary database."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = init_db(db_path)

        # Patch the get_session function to use test database
        import job_track.api.server as server_module
        from job_track.db.models import get_session as original_get_session

        def test_get_session():
            return original_get_session(db_path)

        original = server_module.get_session
        server_module.get_session = test_get_session

        client = TestClient(server_module.app)
        yield client

        server_module.get_session = original
        engine.dispose()


class TestJobEndpoints:
    """Tests for job-related endpoints."""

    def test_list_jobs_empty(self, test_client):
        """Test listing jobs when database is empty."""
        response = test_client.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["jobs"] == []

    def test_create_job(self, test_client):
        """Test creating a new job."""
        job_data = {
            "title": "Software Engineer",
            "company": "TechCorp",
            "location": "Remote",
            "description": "Great opportunity",
            "apply_url": "https://techcorp.com/apply",
            "tags": ["new-grad", "remote"],
        }
        response = test_client.post("/api/jobs", json=job_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Software Engineer"
        assert data["company"] == "TechCorp"
        assert "new-grad" in data["tags"]
        assert data["is_applied"] is False

    def test_get_job(self, test_client):
        """Test getting a specific job."""
        # Create a job first
        job_data = {
            "title": "Data Scientist",
            "company": "DataCorp",
            "apply_url": "https://datacorp.com/apply",
        }
        create_response = test_client.post("/api/jobs", json=job_data)
        job_id = create_response.json()["id"]

        # Get the job
        response = test_client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Data Scientist"

    def test_update_job(self, test_client):
        """Test updating a job."""
        # Create a job first
        job_data = {
            "title": "Product Manager",
            "company": "ProductCo",
            "apply_url": "https://productco.com/apply",
        }
        create_response = test_client.post("/api/jobs", json=job_data)
        job_id = create_response.json()["id"]

        # Update the job
        update_data = {"location": "New York", "tags": ["product", "senior"]}
        response = test_client.patch(f"/api/jobs/{job_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["location"] == "New York"
        assert "product" in response.json()["tags"]

    def test_mark_job_pending(self, test_client):
        """Test marking a job as pending."""
        # Create a job
        job_data = {
            "title": "ML Engineer",
            "company": "MLCorp",
            "apply_url": "https://mlcorp.com/apply",
        }
        create_response = test_client.post("/api/jobs", json=job_data)
        job_id = create_response.json()["id"]

        # Mark as pending
        response = test_client.post(f"/api/jobs/{job_id}/mark-pending")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

        # Verify it's pending
        get_response = test_client.get(f"/api/jobs/{job_id}")
        assert get_response.json()["is_pending"] is True

    def test_confirm_apply(self, test_client):
        """Test confirming a job application."""
        # Create a job
        job_data = {
            "title": "DevOps Engineer",
            "company": "DevOpsCo",
            "apply_url": "https://devopsco.com/apply",
        }
        create_response = test_client.post("/api/jobs", json=job_data)
        job_id = create_response.json()["id"]

        # Confirm application
        response = test_client.post(
            f"/api/jobs/{job_id}/confirm-apply",
            json={"applied": True, "profile_id": "test-profile-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_applied"] is True
        assert data["is_pending"] is False
        assert data["applied_at"] is not None
        assert data["profile_id"] == "test-profile-123"

    def test_delete_job(self, test_client):
        """Test deleting a job."""
        # Create a job
        job_data = {
            "title": "Test Job",
            "company": "TestCo",
            "apply_url": "https://testco.com/apply",
        }
        create_response = test_client.post("/api/jobs", json=job_data)
        job_id = create_response.json()["id"]

        # Delete the job
        response = test_client.delete(f"/api/jobs/{job_id}")
        assert response.status_code == 200

        # Verify it's deleted
        get_response = test_client.get(f"/api/jobs/{job_id}")
        assert get_response.status_code == 404


class TestProfileEndpoints:
    """Tests for profile-related endpoints."""

    def test_list_profiles_empty(self, test_client):
        """Test listing profiles when database is empty."""
        response = test_client.get("/api/profiles")
        assert response.status_code == 200
        assert response.json()["profiles"] == []

    def test_create_profile(self, test_client):
        """Test creating a new profile."""
        profile_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1-555-555-5555",
            "linkedin_url": "https://linkedin.com/in/johndoe",
        }
        response = test_client.post("/api/profiles", json=profile_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"
        assert data["phone"] == "+1-555-555-5555"

    def test_get_profile(self, test_client):
        """Test getting a specific profile."""
        # Create a profile first
        profile_data = {"name": "Jane Smith", "email": "jane@example.com"}
        create_response = test_client.post("/api/profiles", json=profile_data)
        profile_id = create_response.json()["id"]

        # Get the profile
        response = test_client.get(f"/api/profiles/{profile_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Jane Smith"

    def test_update_profile(self, test_client):
        """Test updating a profile."""
        # Create a profile first
        profile_data = {"name": "Bob Builder", "email": "bob@example.com"}
        create_response = test_client.post("/api/profiles", json=profile_data)
        profile_id = create_response.json()["id"]

        # Update the profile
        update_data = {"phone": "+1-555-123-4567"}
        response = test_client.patch(f"/api/profiles/{profile_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["phone"] == "+1-555-123-4567"

    def test_create_profile_with_address(self, test_client):
        """Test creating a profile with address fields."""
        profile_data = {
            "name": "Charlie Brown",
            "email": "charlie@example.com",
            "address_street": "123 Main St",
            "address_city": "Springfield",
            "address_state": "IL",
            "address_zip": "62701",
            "address_country": "USA",
        }
        response = test_client.post("/api/profiles", json=profile_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Charlie Brown"
        assert data["address_street"] == "123 Main St"
        assert data["address_city"] == "Springfield"
        assert data["address_state"] == "IL"
        assert data["address_zip"] == "62701"
        assert data["address_country"] == "USA"

    def test_update_profile_address(self, test_client):
        """Test updating profile address fields."""
        # Create a profile first
        profile_data = {"name": "Dan Smith", "email": "dan@example.com"}
        create_response = test_client.post("/api/profiles", json=profile_data)
        profile_id = create_response.json()["id"]

        # Update with address
        update_data = {
            "address_city": "Boston",
            "address_state": "MA",
        }
        response = test_client.patch(f"/api/profiles/{profile_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["address_city"] == "Boston"
        assert response.json()["address_state"] == "MA"

    def test_delete_profile(self, test_client):
        """Test deleting a profile."""
        # Create a profile
        profile_data = {"name": "Delete Me", "email": "delete@example.com"}
        create_response = test_client.post("/api/profiles", json=profile_data)
        profile_id = create_response.json()["id"]

        # Delete the profile
        response = test_client.delete(f"/api/profiles/{profile_id}")
        assert response.status_code == 200

        # Verify it's deleted
        get_response = test_client.get(f"/api/profiles/{profile_id}")
        assert get_response.status_code == 404


class TestUrlValidation:
    """Tests for URL validation (SSRF prevention)."""

    def test_is_safe_url_blocks_localhost(self):
        """Test that localhost URLs are blocked."""
        from job_track.api.server import is_safe_url

        assert not is_safe_url("http://localhost/test")
        assert not is_safe_url("http://127.0.0.1/test")
        assert not is_safe_url("http://127.0.0.1:8080/test")
        assert not is_safe_url("http://0.0.0.0/test")

    def test_is_safe_url_blocks_non_http(self):
        """Test that non-HTTP schemes are blocked."""
        from job_track.api.server import is_safe_url

        assert not is_safe_url("file:///etc/passwd")
        assert not is_safe_url("ftp://example.com")
        assert not is_safe_url("gopher://example.com")

    def test_is_safe_url_allows_public_urls(self):
        """Test that public HTTP URLs are allowed."""
        from job_track.api.server import is_safe_url

        # Note: These may fail if DNS doesn't resolve
        # but the function should handle that gracefully
        assert is_safe_url("https://example.com/careers")
        assert is_safe_url("https://google.com/jobs")


class TestScrapeEndpoint:
    """Tests for the scrape endpoint."""

    def test_scrape_blocks_internal_urls(self, test_client):
        """Test that internal URLs are blocked in scrape requests."""
        response = test_client.post(
            "/api/scrape",
            json={"urls": ["http://localhost/internal", "http://127.0.0.1/api"]},
        )
        assert response.status_code == 200
        data = response.json()
        # All URLs should be blocked
        assert data["scraped"] == 0
        assert data["added"] == 0
        assert len(data["errors"]) == 2
        assert "not allowed" in data["errors"][0]["error"]
