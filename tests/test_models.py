"""Tests for database models."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Base, Job, Application
from datetime import datetime

TEST_DATABASE_URL = "sqlite:///./test_models.db"


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_create_job(db_session):
    """Test creating a job in the database."""
    job = Job(
        title="Software Engineer",
        company="Tech Corp",
        location="San Francisco, CA",
        description="Great job",
        url="https://example.com/job/1",
        source="test"
    )
    db_session.add(job)
    db_session.commit()
    
    assert job.id is not None
    assert job.title == "Software Engineer"
    assert job.created_at is not None


def test_query_jobs(db_session):
    """Test querying jobs from the database."""
    # Create multiple jobs
    job1 = Job(title="Engineer 1", company="Company A", url="https://example.com/1")
    job2 = Job(title="Engineer 2", company="Company B", url="https://example.com/2")
    
    db_session.add(job1)
    db_session.add(job2)
    db_session.commit()
    
    # Query all jobs
    jobs = db_session.query(Job).all()
    assert len(jobs) == 2


def test_create_application(db_session):
    """Test creating an application in the database."""
    application = Application(
        job_title="Senior Developer",
        company="Big Tech",
        location="Remote",
        status="applied",
        notes="Interesting position"
    )
    db_session.add(application)
    db_session.commit()
    
    assert application.id is not None
    assert application.job_title == "Senior Developer"
    assert application.status == "applied"
    assert application.applied_date is not None


def test_query_applications_by_status(db_session):
    """Test querying applications by status."""
    # Create applications with different statuses
    app1 = Application(job_title="Job 1", company="Company A", status="pending")
    app2 = Application(job_title="Job 2", company="Company B", status="applied")
    app3 = Application(job_title="Job 3", company="Company C", status="pending")
    
    db_session.add_all([app1, app2, app3])
    db_session.commit()
    
    # Query by status
    pending_apps = db_session.query(Application).filter(
        Application.status == "pending"
    ).all()
    assert len(pending_apps) == 2


def test_update_application(db_session):
    """Test updating an application."""
    application = Application(
        job_title="Developer",
        company="Company",
        status="pending"
    )
    db_session.add(application)
    db_session.commit()
    
    # Update status
    application.status = "interview"
    db_session.commit()
    
    # Verify update
    updated = db_session.query(Application).filter(
        Application.id == application.id
    ).first()
    assert updated.status == "interview"


def test_delete_job(db_session):
    """Test deleting a job."""
    job = Job(title="Test Job", company="Test Company", url="https://example.com/test")
    db_session.add(job)
    db_session.commit()
    job_id = job.id
    
    # Delete the job
    db_session.delete(job)
    db_session.commit()
    
    # Verify deletion
    deleted_job = db_session.query(Job).filter(Job.id == job_id).first()
    assert deleted_job is None
