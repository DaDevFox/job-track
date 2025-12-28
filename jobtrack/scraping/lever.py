"""Lever-specific scraper."""

from __future__ import annotations

from urllib.parse import urljoin
import logging

from bs4 import BeautifulSoup

from .. import schemas
from .base import Scraper
from .generic import _looks_new_grad

logger = logging.getLogger(__name__)


def parse_lever_listings(html: str, request: schemas.JobScrapeRequest) -> list[schemas.JobCreate]:
    soup = BeautifulSoup(html, "lxml")
    postings = soup.select("div.posting")
    total_seen = len(postings)
    filtered_new_grad = 0
    jobs: list[schemas.JobCreate] = []
    for posting in postings:
        link = posting.select_one("a.posting-title")
        if not link:
            continue
        title_node = link.select_one("h5") or link
        title = title_node.get_text(strip=True)
        if not title:
            continue
        href = urljoin(str(request.url), link.get("href"))
        location_node = posting.select_one("span.sort-by-location")
        location = location_node.get_text(strip=True) if location_node else None
        description_node = posting.select_one("div.posting-categories")
        description = description_node.get_text(" | ", strip=True) if description_node else None
        tag_nodes = posting.select("div.posting-categories span")
        tags = [node.get_text(strip=True) for node in tag_nodes if node.get_text(strip=True)]
        new_grad = _looks_new_grad(title) or any(_looks_new_grad(tag) for tag in tags)
        if request.new_grad_only and not new_grad:
            filtered_new_grad += 1
            continue
        jobs.append(
            schemas.JobCreate(
                title=title,
                company=request.company,
                location=location,
                description=description,
                apply_url=href,
                source_url=str(request.url),
                tags=tags + (["new-grad"] if new_grad else []),
                new_grad=new_grad,
            )
        )
        if len(jobs) >= request.limit:
            break
    logger.debug(
        "Lever parse stats url=%s total=%s kept=%s filtered_new_grad=%s",
        request.url,
        total_seen,
        len(jobs),
        filtered_new_grad,
    )
    if request.new_grad_only and len(jobs) == 0 and filtered_new_grad:
        logger.warning(
            "Lever new-grad filter removed %s/%s postings for %s",
            filtered_new_grad,
            total_seen,
            request.url,
        )
    return jobs


class LeverScraper(Scraper):
    """Scraper that knows how to parse Lever-hosted job boards."""

    name = "lever"

    async def fetch(self, client, request: schemas.JobScrapeRequest):
        response = await client.get(str(request.url))
        response.raise_for_status()
        return parse_lever_listings(response.text, request)
