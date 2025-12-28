"""Filesystem helpers for resume storage."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from fastapi import UploadFile

from .config import get_settings

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _sanitize_filename(filename: str) -> str:
    stem = _FILENAME_SAFE.sub("_", filename.strip()) or "resume.pdf"
    return stem


def resume_destination(profile_id: UUID, filename: str) -> Path:
    settings = get_settings()
    profile_dir = settings.resume_dir / str(profile_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    safe_name = _sanitize_filename(filename)
    return profile_dir / f"{timestamp}-{safe_name}"


def persist_upload(profile_id: UUID, upload: UploadFile) -> Path:
    destination = resume_destination(profile_id, upload.filename or "resume.pdf")
    with destination.open("wb") as file_handle:
        copy_stream(upload.file, file_handle)
    return destination


def copy_stream(source: BinaryIO, destination: BinaryIO, chunk_size: int = 64 * 1024) -> None:
    while chunk := source.read(chunk_size):
        destination.write(chunk)
