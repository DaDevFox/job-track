"""API routers."""

from fastapi import APIRouter

from . import jobs, profiles, scraped, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(scraped.router, prefix="/scraped", tags=["scraped"])
