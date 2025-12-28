"""Very small heuristic scraper for simple HTML listings."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from .. import schemas
from .base import Scraper

logger = logging.getLogger(__name__)

_KEYWORDS = ("new grad", "new-grad", "newgrad", "new graduate", "university", "entry level", "entry-level")


def _looks_new_grad(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _KEYWORDS)


def _extract_text(node) -> str:
    return " ".join(node.stripped_strings)


def parse_basic_listing(html: str, request: schemas.JobScrapeRequest) -> list[schemas.JobCreate]:
    soup = BeautifulSoup(html, "lxml")
    candidates = soup.select("[data-job-id], article, li, div")
    jobs: list[schemas.JobCreate] = []
    seen_urls: set[str] = set()
    filtered_new_grad = 0
    for element in candidates:
        link = element.find("a", href=True)
        if not link:
            continue
        href = link.get("href")
        if not href or href.startswith("#"):
            continue
        title = link.get_text(strip=True)
        if not title:
            continue
        location_node = element.find(attrs={"data-location": True}) or element.find(class_="location")
        description_node = element.find(class_="description")
        location_text = location_node.get_text(strip=True) if location_node else None
        description_text = (
            _extract_text(description_node)
            if description_node
            else _extract_text(element)
        )
        new_grad = _looks_new_grad(title) or (description_text and _looks_new_grad(description_text))
        if request.new_grad_only and not new_grad:
            filtered_new_grad += 1
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)
        jobs.append(
            schemas.JobCreate(
                title=title,
                company=request.company,
                location=location_text,
                description=description_text[:5000] if description_text else None,
                apply_url=href,
                source_url=str(request.url),
                tags=["new-grad"] if new_grad else [],
                new_grad=new_grad,
            )
        )
        if len(jobs) >= request.limit:
            break
    logger.debug(
        "Generic scrape stats url=%s total_candidates=%s kept=%s filtered_new_grad=%s",
        request.url,
        len(candidates),
        len(jobs),
        filtered_new_grad,
    )
    if request.new_grad_only and len(jobs) == 0 and filtered_new_grad:
        logger.warning(
            "Generic scraper filtered every posting due to new-grad requirement for %s",
            request.url,
        )
    return jobs


class GenericHTMLScraper(Scraper):
    """Fallback scraper that uses very simple heuristics."""

    name = "generic"

    async def fetch(self, client, request: schemas.JobScrapeRequest):
        response = await client.get(str(request.url))
        response.raise_for_status()
        return parse_basic_listing(response.text, request)
