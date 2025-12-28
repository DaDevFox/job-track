#!/usr/bin/env python3
"""Integration test for TUI and API."""
import pytest
import httpx


@pytest.mark.asyncio
async def test_integration():
    """Test that TUI can connect to API."""
    API_BASE_URL = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # Test root endpoint
        response = await client.get(f"{API_BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Job Track API"
        
        # Test getting jobs
        response = await client.get(f"{API_BASE_URL}/jobs")
        assert response.status_code == 200
        jobs = response.json()
        assert isinstance(jobs, list)
        
        # Test getting applications
        response = await client.get(f"{API_BASE_URL}/applications")
        assert response.status_code == 200
        apps = response.json()
        assert isinstance(apps, list)
