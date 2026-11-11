"""Abstract base class for dataset parsers.

Each parser transforms raw API response data into a structured
pandas DataFrame with consistent column naming.
"""

import abc
import logging
from typing import Any, Dict, List

import pandas as pd


class BaseParser(abc.ABC):
    """Abstract base for dataset-specific parsers.

    Subclasses implement `parse` to transform raw API JSON
    into a clean pandas DataFrame.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = logging.getLogger(f"nse_pulse.parser.{name}")

    @abc.abstractmethod
    def parse(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """Parse raw API response into a structured DataFrame.

        Args:
            raw_data: Dictionary of raw API responses keyed by sub-endpoint.

        Returns:
            Parsed and flattened DataFrame.

        Raises:
            ValueError: If the response format is unexpected.
        """
        ...

    def _extract_records(
        self,
        data: Any,
        data_key: str = "data",
    ) -> List[Dict[str, Any]]:
        """Safely extract record list from API response.

        NSE responses typically nest records under a 'data' key,
        but the structure varies. This method handles common patterns.

        Args:
            data: Raw response (dict or list).
            data_key: Key name to look for records under.

        Returns:
            List of record dictionaries.
        """
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Check for error responses
            if "error" in data:
                self.logger.warning(
                    "Response contains error: %s",
                    data["error"],
                )
                return []

            # Try the specified key
            if data_key in data:
                records = data[data_key]
                if isinstance(records, list):
                    return records
                self.logger.warning(
                    "Expected list under '%s', got %s",
                    data_key,
                    type(records).__name__,
                )
                return []

            # Some endpoints nest under index names (e.g., 'NIFTY')
            for key, value in data.items():
                if isinstance(value, dict) and data_key in value:
                    nested = value[data_key]
                    if isinstance(nested, list):
                        self.logger.debug(
                            "Found records under nested key '%s.%s'",
                            key,
                            data_key,
                        )
                        return nested

            self.logger.warning(
                "Could not find '%s' key in response. Available keys: %s",
                data_key,
                list(data.keys()),
            )
            return []

        self.logger.warning(
            "Unexpected response type: %s",
            type(data).__name__,
        )
        return []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"

