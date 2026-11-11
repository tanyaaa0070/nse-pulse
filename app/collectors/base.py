"""Abstract base class for all dataset collectors.

Each dataset has its own collector that inherits from BaseCollector
and implements the `fetch` method to retrieve raw data from NSE.
"""

import abc
import logging
from typing import Any, Dict

from app.collectors.nse_client import NSEClient


class BaseCollector(abc.ABC):
    """Abstract base for dataset-specific data collectors.

    Attributes:
        name: Machine-readable dataset identifier (e.g. 'top-gainers-losers').
        display_name: Human-readable name for logging.
        client: Shared NSEClient instance for HTTP requests.
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        client: NSEClient,
    ) -> None:
        self.name = name
        self.display_name = display_name
        self.client = client
        self.logger = logging.getLogger(f"nse_pulse.collector.{name}")

    @abc.abstractmethod
    def fetch(self) -> Dict[str, Any]:
        """Fetch raw data from NSE API.

        Returns:
            Dictionary with sub-endpoint keys mapped to their raw JSON responses.
            Example: {"gainers": [...], "losers": [...]}

        Raises:
            ConnectionError: If the endpoint is unreachable after retries.
            ValueError: If the response format is unexpected.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"

