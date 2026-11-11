"""Collector for 52-Week High Equity dataset.

Fetches stocks that have reached their 52-week high price
from NSE's live analysis API.
"""

from typing import Any, Dict

from app.collectors.base import BaseCollector
from app.collectors.nse_client import NSEClient
from app.config.settings import DatasetConfig


class Week52HighCollector(BaseCollector):
    """Collects 52-week high equity data from NSE."""

    def __init__(self, client: NSEClient) -> None:
        config = DatasetConfig.get_config("52-week-high-equity")
        super().__init__(
            name="52-week-high-equity",
            display_name=config["name"],  # type: ignore[index]
            client=client,
        )
        self._endpoints = config["endpoints"]  # type: ignore[index]

    def fetch(self) -> Dict[str, Any]:
        """Fetch 52-week high equity data.

        Returns:
            Dict with 'week52_high' key containing the raw API response.
        """
        results: Dict[str, Any] = {}

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
                results[key] = {"error": str(exc), "data": []}

        return results

