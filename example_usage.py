#!/usr/bin/env python3
"""Example usage of Job Track API programmatically."""
import requests
import json
from datetime import datetime


def main():
    """Demonstrate API usage."""
    API_BASE_URL = "http://localhost:8000"
    
    print("=" * 60)
    print("Job Track API Example Usage")
    print("=" * 60)
    
    # 1. Check API is running
    print("\n1. Checking API status...")
    response = requests.get(f"{API_BASE_URL}/")
    print(f"   API Status: {response.json()['message']}")
    
    # 2. Scrape some jobs
    print("\n2. Scraping jobs...")
    response = requests.post(
        f"{API_BASE_URL}/scrape",
        params={"search_term": "python developer", "location": "remote"}
    )
    result = response.json()
    print(f"   {result['message']}")
    
    # 3. List all jobs
    print("\n3. Listing all jobs...")
    response = requests.get(f"{API_BASE_URL}/jobs")
    jobs = response.json()
    print(f"   Found {len(jobs)} jobs:")
    for job in jobs[:3]:  # Show first 3
        print(f"   - {job['title']} at {job['company']}")
    
    # 4. Create a job application
    print("\n4. Creating a new application...")
    app_data = {
        "job_title": "Senior Python Developer",
        "company": "Example Corp",
        "location": "Remote",
        "status": "pending",
        "notes": "Great opportunity, need to prepare for interview",
        "cover_letter": True
    }
    response = requests.post(f"{API_BASE_URL}/applications", json=app_data)
    new_app = response.json()
    print(f"   Created application #{new_app['id']}")
    
    # 5. List all applications
    print("\n5. Listing all applications...")
    response = requests.get(f"{API_BASE_URL}/applications")
    applications = response.json()
    print(f"   Found {len(applications)} applications:")
    for app in applications:
        print(f"   - {app['job_title']} at {app['company']} - Status: {app['status']}")
    
    # 6. Update application status
    print("\n6. Updating application status...")
    app_id = new_app['id']
    response = requests.patch(
        f"{API_BASE_URL}/applications/{app_id}",
        json={"status": "applied"}
    )
    updated_app = response.json()
    print(f"   Updated application #{app_id} to '{updated_app['status']}'")
    
    # 7. Filter applications by status
    print("\n7. Filtering applications by status...")
    response = requests.get(f"{API_BASE_URL}/applications?status=applied")
    applied_apps = response.json()
    print(f"   Found {len(applied_apps)} applications with status 'applied'")
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Start the TUI: python -m tui.app")
    print("- View API docs: http://localhost:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API server.")
        print("Please start the API server first:")
        print("  ./start_api.sh")
        print("  or")
        print("  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")
