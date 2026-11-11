"""Configuration management using Pydantic Settings.

All application configuration is loaded from environment variables
with sensible defaults. Use a .env file for local development.
"""

from pathlib import Path
from typing import ClassVar, Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class DatasetConfig:
    """Registry mapping CLI dataset names to their API endpoints and CSV prefixes.

    Each dataset entry contains:
        - name: Human-readable display name
        - endpoints: Dict of sub-endpoint keys to URL paths (relative to base)
        - csv_prefix: Prefix used for generated CSV filenames
    """

    DATASETS: ClassVar[Dict[str, dict]] = {
        "top-gainers-losers": {
            "name": "Top Gainers & Losers",
            "endpoints": {
                "gainers": "/api/live-analysis/gainers/allSec",
                "losers": "/api/live-analysis/losers/allSec",
            },
            "csv_prefix": "top_gainers_losers",
        },
        "upper-band-hitters": {
            "name": "Upper Band Hitters",
            "endpoints": {
                "upper_band": "/api/live-analysis/upperband/allSec",
            },
            "csv_prefix": "upper_band_hitters",
        },
        "volume-gainers-spurts": {
            "name": "Volume Gainers / Spurts",
            "endpoints": {
                "volume": "/api/live-analysis/volume-gainers",
            },
            "csv_prefix": "volume_gainers_spurts",
        },
        "52-week-high-equity": {
            "name": "52-Week High Equity",
            "endpoints": {
                "week52_high": "/api/live-analysis/52-week-high",
            },
            "csv_prefix": "52_week_high_equity",
        },
    }

    @classmethod
    def get_dataset_names(cls) -> List[str]:
        """Return all registered dataset CLI names."""
        return list(cls.DATASETS.keys())

    @classmethod
    def get_config(cls, name: str) -> Optional[dict]:
        """Get configuration for a specific dataset by CLI name."""
        return cls.DATASETS.get(name)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Defaults are production-safe. Override via .env or environment variables.
    """

    # NSE Configuration
    nse_base_url: str = Field(
        default="https://www.nseindia.com",
        description="Base URL for NSE India website",
    )
    nse_request_timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds",
    )
    nse_retry_count: int = Field(
        default=3,
        description="Maximum number of retry attempts per request",
    )
    nse_retry_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff multiplier between retries",
    )
    nse_rate_limit_delay: float = Field(
        default=1.5,
        description="Minimum delay between consecutive API requests (seconds)",
    )

    # Storage Paths
    output_dir: Path = Field(
        default=Path("data/processed"),
        description="Directory for final CSV output files",
    )
    raw_output_dir: Path = Field(
        default=Path("data/raw"),
        description="Directory for raw API response snapshots",
    )
    reports_dir: Path = Field(
        default=Path("data/reports"),
        description="Directory for JSON execution reports",
    )

    # Logging
    log_dir: Path = Field(
        default=Path("logs"),
        description="Directory for structured log files",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Database (optional)
    db_enabled: bool = Field(
        default=False,
        description="Enable PostgreSQL storage (requires DATABASE_URL)",
    )
    database_url: str = Field(
        default="postgresql://nse_user:nse_password@localhost:5432/nse_pulse",
        description="PostgreSQL connection string",
    )

    # Scheduler (optional)
    scheduler_enabled: bool = Field(
        default=False,
        description="Enable periodic scheduled execution",
    )
    scheduler_interval_minutes: int = Field(
        default=60,
        description="Interval between scheduled pipeline runs (minutes)",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def ensure_directories(self) -> None:
        """Create all required output directories if they don't exist."""
        for dir_path in [
            self.output_dir,
            self.raw_output_dir,
            self.reports_dir,
            self.log_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Factory function to create a Settings instance.

    Each call creates a fresh instance to pick up any env changes.
    For caching, use functools.lru_cache at the call site.
    """
    return Settings()

