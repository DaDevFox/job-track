"""Application configuration helpers."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables."""

    app_name: str = "JobTrack"
    api_host: str = "127.0.0.1"
    api_port: int = 8787
    database_url: str = Field(default_factory=lambda: f"sqlite:///{Path('data/jobtrack.db').resolve()}")
    scraped_database_url: str = Field(default_factory=lambda: f"sqlite:///{Path('data/scraped_jobs.db').resolve()}")
    data_dir: Path = Field(default_factory=lambda: Path("data").resolve())
    resume_dir: Path = Field(default_factory=lambda: Path("data/resumes").resolve())

    model_config = SettingsConfigDict(env_prefix="JOBTRACK_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def ensure_directories(self) -> None:
        """Create on-disk folders for runtime data."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.resume_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Return a cached settings instance and ensure directories exist."""
    settings = Settings()
    settings.ensure_directories()
    return settings
