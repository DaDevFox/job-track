"""Pydantic schemas for API validation."""
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional


class JobBase(BaseModel):
    """Base job schema."""
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    url: str
    source: Optional[str] = None


class JobCreate(JobBase):
    """Schema for creating a job."""
    pass


class Job(JobBase):
    """Schema for job response."""
    id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ApplicationBase(BaseModel):
    """Base application schema."""
    job_title: str
    company: str
    location: Optional[str] = None
    job_url: Optional[str] = None
    status: str = "pending"
    notes: Optional[str] = None
    resume_version: Optional[str] = None
    cover_letter: bool = False


class ApplicationCreate(ApplicationBase):
    """Schema for creating an application."""
    pass


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    job_url: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    resume_version: Optional[str] = None
    cover_letter: Optional[bool] = None


class Application(ApplicationBase):
    """Schema for application response."""
    id: int
    applied_date: datetime
    
    model_config = {"from_attributes": True}
