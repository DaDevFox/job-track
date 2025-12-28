"""Quick manual smoke test for the JobTrack API."""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import httpx

API_BASE = os.getenv("JOBTRACK_API_URL", "http://127.0.0.1:8787/api")


async def main() -> None:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        resp = await client.get("/jobs", params={"new_grad_only": True, "only_unapplied": True})
        print("Initial jobs", resp.status_code, resp.json())

        profile_payload = {
            "label": "Smoke Test",
            "full_name": "CLI User",
            "email": "cli@example.com",
        }
        profile_resp = await client.post("/profiles", json=profile_payload)
        profile_resp.raise_for_status()
        profile_data = profile_resp.json()
        print("Profile", json.dumps(profile_data, indent=2))

        job_payload = {
            "title": "Smoke SWE",
            "company": "ExampleCo",
            "apply_url": f"https://example.com/jobs/{uuid.uuid4()}",
            "source_url": "https://example.com/jobs",
            "new_grad": True,
        }
        job_resp = await client.post("/jobs", json=job_payload)
        job_resp.raise_for_status()
        job_data = job_resp.json()
        print("Job", json.dumps(job_data, indent=2))

        await client.post(f"/jobs/{job_data['id']}/pending", json={"pending": True})
        await client.post(
            f"/jobs/{job_data['id']}/applied",
            json={"profile_id": profile_data["id"], "mark_applied": True},
        )

        final = await client.get("/jobs", params={"new_grad_only": True, "only_unapplied": False})
        final.raise_for_status()
        print("Final jobs count", len(final.json()))


if __name__ == "__main__":
    asyncio.run(main())
