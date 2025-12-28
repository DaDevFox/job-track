"""Scraper base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging

import httpx

from .. import schemas

logger = logging.getLogger(__name__)


class Scraper(ABC):
    """Base interface for a job board scraper."""

    name: str

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient, request: schemas.JobScrapeRequest) -> list[schemas.JobCreate]:
        raise NotImplementedError


class Registry(dict[str, Scraper]):
    """Scraper registry that falls back to the generic parser."""

    def get_scraper(self, key: str) -> Scraper:
        if key in self:
            return self[key]
        return self["generic"]


async def run_scraper(request: schemas.JobScrapeRequest) -> list[schemas.JobCreate]:
    """Run the configured scraper for the incoming request."""
    scraper = SCRAPERS.get_scraper(request.source)
    logger.info(
        "Starting scrape source=%s url=%s new_grad_only=%s limit=%s",
        scraper.name,
        request.url,
        request.new_grad_only,
        request.limit,
    )
    async with httpx.AsyncClient(timeout=30) as client:
        jobs = await scraper.fetch(client, request)
    logger.info(
        "Finished scrape source=%s url=%s fetched=%s",
        scraper.name,
        request.url,
        len(jobs),
    )
    return jobs


from .generic import GenericHTMLScraper  # noqa: E402
from .lever import LeverScraper  # noqa: E402

SCRAPERS = Registry(
    {
        "generic": GenericHTMLScraper(),
        "lever": LeverScraper(),
    }
)
