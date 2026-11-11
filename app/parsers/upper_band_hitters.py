"""Parser for Upper Band Hitters dataset.

Transforms the raw NSE upper band hitters API response into a
structured DataFrame.
"""

from typing import Any, Dict

import pandas as pd

from app.parsers.base import BaseParser


class UpperBandHittersParser(BaseParser):
    """Parses upper band hitters data into a DataFrame."""

    EXPECTED_COLUMNS = [
        "symbol", "series", "open_price", "high_price", "low_price",
        "ltp", "prev_close", "change", "pct_change", "traded_qty",
        "trade_date",
    ]

    FIELD_MAP: Dict[str, str] = {
        "symbol": "symbol",
        "series": "series",
        "openPrice": "open_price",
        "highPrice": "high_price",
        "lowPrice": "low_price",
        "lastPrice": "ltp",
        "ltp": "ltp",
        "previousPrice": "prev_close",
        "previousClose": "prev_close",
        "prevClose": "prev_close",
        "pChange": "pct_change",
        "perChange": "pct_change",
        "change": "change",
        "netPrice": "change",
        "totalTradedVolume": "traded_qty",
        "tradedQuantity": "traded_qty",
        "date": "trade_date",
    }

    def __init__(self) -> None:
        super().__init__(name="upper-band-hitters")

    def parse(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """Parse upper band hitters into a DataFrame.

        Args:
            raw_data: Dict with 'upper_band' sub-response.

        Returns:
            DataFrame with standardized columns.
        """
        sub_data = raw_data.get("upper_band", {})
        records = self._extract_records(sub_data)

        self.logger.info("Parsed %d upper band hitter records", len(records))

        if not records:
            self.logger.warning("No records found in upper band hitters response")
            return pd.DataFrame(columns=self.EXPECTED_COLUMNS)

        df = pd.DataFrame(records)
        df = self._rename_columns(df)
        return self._select_columns(df)

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename API columns to standardized names."""
        rename_map = {}
        for api_col, std_col in self.FIELD_MAP.items():
            if api_col in df.columns:
                rename_map[api_col] = std_col
        return df.rename(columns=rename_map)

    def _select_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Select and order expected columns, adding missing ones as NaN."""
        for col in self.EXPECTED_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df[self.EXPECTED_COLUMNS]

