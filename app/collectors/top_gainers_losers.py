"""Collector for Top Gainers & Losers dataset.

Fetches both gainers and losers data from NSE's live analysis API
and combines them into a single response.
"""

from typing import Any, Dict

from app.collectors.base import BaseCollector
from app.collectors.nse_client import NSEClient
from app.config.settings import DatasetConfig


class TopGainersLosersCollector(BaseCollector):
    """Collects top gainers and losers market data from NSE."""

    def __init__(self, client: NSEClient) -> None:
        config = DatasetConfig.get_config("top-gainers-losers")
        super().__init__(
            name="top-gainers-losers",
            display_name=config["name"],  # type: ignore[index]
            client=client,
        )
        self._endpoints = config["endpoints"]  # type: ignore[index]

    def fetch(self) -> Dict[str, Any]:
        """Fetch top gainers and losers data.

        Returns:
            Dict with 'gainers' and 'losers' keys, each containing
            the raw API response (typically with a 'data' list).
        """
        results: Dict[str, Any] = {}

        for key, endpoint in self._endpoints.items():
            self.logger.info("Fetching %s from %s", key, endpoint)
            try:
                data = self.client.get(endpoint)
                results[key] = data
                record_count = len(data.get("data", data.get("NIFTY", {}).get("data", [])))
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

