"""Tests for the FastAPI backend."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app, get_db
from backend.models import Base

# Test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    """Create test client."""
    return TestClient(app)


def test_read_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "Job Track API"


def test_create_job(client):
    """Test creating a job."""
    job_data = {
        "title": "Software Engineer",
        "company": "Tech Corp",
        "location": "San Francisco, CA",
        "description": "Great opportunity",
        "url": "https://example.com/job/1"
    }
    response = client.post("/jobs", json=job_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == job_data["title"]
    assert data["company"] == job_data["company"]
    assert "id" in data


def test_get_jobs(client):
    """Test getting all jobs."""
    # Create a job first
    job_data = {
        "title": "Data Scientist",
        "company": "AI Company",
        "url": "https://example.com/job/2"
    }
    client.post("/jobs", json=job_data)
    
    # Get all jobs
    response = client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) >= 1
    assert jobs[0]["title"] == job_data["title"]


def test_get_job_by_id(client):
    """Test getting a specific job."""
    # Create a job
    job_data = {
        "title": "DevOps Engineer",
        "company": "Cloud Services",
        "url": "https://example.com/job/3"
    }
    create_response = client.post("/jobs", json=job_data)
    job_id = create_response.json()["id"]
    
    # Get the job
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["title"] == job_data["title"]


def test_get_nonexistent_job(client):
    """Test getting a job that doesn't exist."""
    response = client.get("/jobs/9999")
    assert response.status_code == 404


def test_delete_job(client):
    """Test deleting a job."""
    # Create a job
    job_data = {
        "title": "Product Manager",
        "company": "Startup",
        "url": "https://example.com/job/4"
    }
    create_response = client.post("/jobs", json=job_data)
    job_id = create_response.json()["id"]
    
    # Delete the job
    response = client.delete(f"/jobs/{job_id}")
    assert response.status_code == 200
    
    # Verify it's deleted
    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 404


def test_create_application(client):
    """Test creating an application."""
    app_data = {
        "job_title": "Senior Engineer",
        "company": "Big Tech",
        "location": "Remote",
        "status": "applied"
    }
    response = client.post("/applications", json=app_data)
    assert response.status_code == 200
    data = response.json()
    assert data["job_title"] == app_data["job_title"]
    assert data["status"] == app_data["status"]
    assert "id" in data


def test_get_applications(client):
    """Test getting all applications."""
    # Create an application
    app_data = {
        "job_title": "Frontend Developer",
        "company": "Web Agency",
        "status": "pending"
    }
    client.post("/applications", json=app_data)
    
    # Get all applications
    response = client.get("/applications")
    assert response.status_code == 200
    applications = response.json()
    assert len(applications) >= 1


def test_get_applications_by_status(client):
    """Test filtering applications by status."""
    # Create applications with different statuses
    app1 = {
        "job_title": "Backend Developer",
        "company": "Company A",
        "status": "applied"
    }
    app2 = {
        "job_title": "Full Stack Developer",
        "company": "Company B",
        "status": "interview"
    }
    client.post("/applications", json=app1)
    client.post("/applications", json=app2)
    
    # Filter by status
    response = client.get("/applications?status=applied")
    assert response.status_code == 200
    applications = response.json()
    assert all(app["status"] == "applied" for app in applications)


def test_update_application(client):
    """Test updating an application."""
    # Create an application
    app_data = {
        "job_title": "QA Engineer",
        "company": "Testing Co",
        "status": "pending"
    }
    create_response = client.post("/applications", json=app_data)
    app_id = create_response.json()["id"]
    
    # Update the application
    update_data = {"status": "interview"}
    response = client.patch(f"/applications/{app_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["status"] == "interview"


def test_delete_application(client):
    """Test deleting an application."""
    # Create an application
    app_data = {
        "job_title": "Security Engineer",
        "company": "SecureCorp",
        "status": "pending"
    }
    create_response = client.post("/applications", json=app_data)
    app_id = create_response.json()["id"]
    
    # Delete the application
    response = client.delete(f"/applications/{app_id}")
    assert response.status_code == 200
    
    # Verify it's deleted
    get_response = client.get(f"/applications/{app_id}")
    assert get_response.status_code == 404


def test_scrape_jobs(client):
    """Test job scraping endpoint."""
    response = client.post("/scrape?search_term=python developer&location=remote")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "jobs_created" in data
    assert data["jobs_found"] > 0
