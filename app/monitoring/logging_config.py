"""Structured logging configuration for NSE Pulse.

Provides JSON-formatted logging with execution context including
timestamps, dataset names, and processing metrics.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra context fields if present
        for field in [
            "dataset", "status", "http_status", "records_fetched",
            "records_valid", "records_rejected", "duration_seconds",
            "retry_attempt", "error_detail", "run_id",
        ]:
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
) -> logging.Logger:
    """Configure application-wide structured logging.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR).
        log_dir: Directory for log files. If None, logs only to console.

    Returns:
        Root logger for the nse_pulse namespace.
    """
    root_logger = logging.getLogger("nse_pulse")
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler with human-readable format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(console_handler)

    # File handler with JSON format
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"nse_pulse_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    return root_logger

