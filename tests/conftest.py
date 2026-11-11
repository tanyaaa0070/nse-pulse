"""Shared Pytest fixtures and mock NSE response payloads."""

from datetime import date
from pathlib import Path
from typing import Any, Dict
import pytest

from app.config.settings import Settings


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Settings instance pointing to isolated temporary directories."""
    return Settings(
        nse_base_url="https://www.nseindia.com",
        nse_request_timeout=5,
        nse_retry_count=2,
        nse_retry_backoff_factor=1.1,
        nse_rate_limit_delay=0.0,
        output_dir=tmp_path / "data" / "processed",
        raw_output_dir=tmp_path / "data" / "raw",
        reports_dir=tmp_path / "data" / "reports",
        log_dir=tmp_path / "logs",
        log_level="DEBUG",
        db_enabled=False,
    )


@pytest.fixture
def sample_gainers_payload() -> Dict[str, Any]:
    return {
        "data": [
            {
                "symbol": "INFY",
                "series": "EQ",
                "openPrice": "1,500.00",
                "highPrice": "1,550.00",
                "lowPrice": "1,490.00",
                "lastPrice": "1,540.00",
                "previousPrice": "1,480.00",
                "change": "60.00",
                "pChange": "4.05",
                "totalTradedVolume": "1,250,000",
                "date": "11-Nov-2026",
            },
            {
                "symbol": "TCS",
                "series": "EQ",
                "openPrice": "3,400.00",
                "highPrice": "3,480.00",
                "lowPrice": "3,390.00",
                "lastPrice": "3,460.00",
                "previousPrice": "3,380.00",
                "change": "80.00",
                "pChange": "2.37",
                "totalTradedVolume": "950,000",
                "date": "11-Nov-2026",
            },
        ]
    }


@pytest.fixture
def sample_losers_payload() -> Dict[str, Any]:
    return {
        "data": [
            {
                "symbol": "RELIANCE",
                "series": "EQ",
                "openPrice": "2,450.00",
                "highPrice": "2,460.00",
                "lowPrice": "2,380.00",
                "lastPrice": "2,390.00",
                "previousPrice": "2,440.00",
                "change": "-50.00",
                "pChange": "-2.05",
                "totalTradedVolume": "2,100,000",
                "date": "11-Nov-2026",
            }
        ]
    }


@pytest.fixture
def sample_upper_band_payload() -> Dict[str, Any]:
    return {
        "data": [
            {
                "symbol": "TATAMOTORS",
                "series": "EQ",
                "openPrice": "720.00",
                "highPrice": "792.00",
                "lowPrice": "720.00",
                "lastPrice": "792.00",
                "previousPrice": "720.00",
                "change": "72.00",
                "pChange": "10.00",
                "totalTradedVolume": "8,500,000",
                "date": "11-Nov-2026",
            }
        ]
    }


@pytest.fixture
def sample_volume_gainers_payload() -> Dict[str, Any]:
    return {
        "data": [
            {
                "symbol": "HDFCBANK",
                "series": "EQ",
                "lastPrice": "1,650.00",
                "change": "35.00",
                "pChange": "2.17",
                "previousPrice": "1,615.00",
                "totalTradedVolume": "15,000,000",
                "avgVolume": "3,000,000",
                "volumeChangePercent": "400.0",
                "date": "11-Nov-2026",
            }
        ]
    }


@pytest.fixture
def sample_52_week_high_payload() -> Dict[str, Any]:
    return {
        "data": [
            {
                "symbol": "BHARTIARTL",
                "series": "EQ",
                "lastPrice": "1,220.00",
                "change": "25.00",
                "pChange": "2.09",
                "previousPrice": "1,195.00",
                "yearHighPrice": "1,220.00",
                "yearLowPrice": "750.00",
                "totalTradedVolume": "4,200,000",
                "date": "11-Nov-2026",
            }
        ]
    }

