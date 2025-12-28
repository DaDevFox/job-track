"""Database models for job tracking application."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

Base = declarative_base()


class Job(Base):
    """Job listing model."""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    company = Column(String, nullable=False, index=True)
    location = Column(String)
    description = Column(Text)
    url = Column(String, nullable=False)
    source = Column(String)  # Where the job was scraped from
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Application(Base):
    """Job application tracking model."""
    
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    job_url = Column(String)
    status = Column(String, default="pending")  # pending, applied, interview, rejected, accepted
    applied_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text)
    resume_version = Column(String)
    cover_letter = Column(Boolean, default=False)


# Database setup
DATABASE_URL = "sqlite:///./jobtrack.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
