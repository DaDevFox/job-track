"""Database engine and helpers."""

from __future__ import annotations

from functools import lru_cache

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings


@lru_cache
def _get_engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, echo=False, connect_args=connect_args)


@lru_cache
def _get_scraped_engine():
    settings = get_settings()
    url = settings.scraped_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create database tables if they do not exist."""
    SQLModel.metadata.create_all(_get_engine())


def init_scraped_db() -> None:
    """Create scraped-job tables in the secondary database."""
    from .models import SCRAPED_METADATA  # Import locally to avoid circular deps

    SCRAPED_METADATA.create_all(_get_scraped_engine())


def get_session():  # pragma: no cover - FastAPI dependency wrapper
    """FastAPI dependency that yields a DB session."""
    engine = _get_engine()
    with Session(engine) as session:
        yield session


def get_scraped_session():  # pragma: no cover - FastAPI dependency wrapper
    """Dependency that yields a scraped DB session."""
    engine = _get_scraped_engine()
    with Session(engine) as session:
        yield session
