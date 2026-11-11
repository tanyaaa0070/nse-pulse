"""Collector for Upper Band Hitters dataset.

Fetches stocks that have hit their upper price band (circuit limit)
from NSE's live analysis API.
"""

from typing import Any, Dict

from app.collectors.base import BaseCollector
from app.collectors.nse_client import NSEClient
from app.config.settings import DatasetConfig


class UpperBandHittersCollector(BaseCollector):
    """Collects upper band hitters data from NSE."""

    def __init__(self, client: NSEClient) -> None:
        config = DatasetConfig.get_config("upper-band-hitters")
        super().__init__(
            name="upper-band-hitters",
            display_name=config["name"],  # type: ignore[index]
            client=client,
        )
        self._endpoints = config["endpoints"]  # type: ignore[index]

    def fetch(self) -> Dict[str, Any]:
        """Fetch upper band hitters data.

        Returns:
            Dict with 'upper_band' key containing the raw API response.
        """
        results: Dict[str, Any] = {}
        errors = []

        for key, endpoint in self._endpoints.items():
            self.logger.info("Fetching %s from %s", key, endpoint)
            try:
                data = self.client.get(endpoint)
                results[key] = data
                record_count = len(data.get("data", []))
                self.logger.info(
                    "Fetched %s: %d records",
                    key,
                    record_count,
                    extra={"dataset": self.name, "status": "success"},
                )
            except (ConnectionError, ValueError) as exc:
                self.logger.error(
                    "Failed to fetch %s: %s",
                    key,
                    exc,
                    extra={"dataset": self.name, "status": "failed"},
                )
                errors.append(str(exc))

        if errors and not results:
            raise ConnectionError(f"Failed to fetch {self.name}: {'; '.join(errors)}")

        return results

