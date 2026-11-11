"""Parser for 52-Week High Equity dataset.

Transforms the raw NSE 52-week high API response into a
structured DataFrame.
"""

from typing import Any, Dict

import pandas as pd

from app.parsers.base import BaseParser


class Week52HighParser(BaseParser):
    """Parses 52-week high equity data into a DataFrame."""

    EXPECTED_COLUMNS = [
        "symbol", "series", "ltp", "change", "pct_change",
        "prev_close", "high_52_week", "low_52_week",
        "traded_qty", "trade_date",
    ]

    FIELD_MAP: Dict[str, str] = {
        "symbol": "symbol",
        "sym": "symbol",
        "series": "series",
        "lastPrice": "ltp",
        "ltp": "ltp",
        "change": "change",
        "pChange": "pct_change",
        "perChange": "pct_change",
        "previousPrice": "prev_close",
        "previousClose": "prev_close",
        "prevClose": "prev_close",
        "yearHighPrice": "high_52_week",
        "wkhi": "high_52_week",
        "high52": "high_52_week",
        "yearLowPrice": "low_52_week",
        "wklo": "low_52_week",
        "low52": "low_52_week",
        "totalTradedVolume": "traded_qty",
        "tradedQuantity": "traded_qty",
        "date": "trade_date",
    }

    def __init__(self) -> None:
        super().__init__(name="52-week-high-equity")

    def parse(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """Parse 52-week high equity data into a DataFrame.

        Args:
            raw_data: Dict with 'week52_high' sub-response.

        Returns:
            DataFrame with standardized columns.
        """
        sub_data = raw_data.get("week52_high", {})
        records = self._extract_records(sub_data)

        self.logger.info("Parsed %d 52-week high records", len(records))

        if not records:
            self.logger.warning("No records found in 52-week high response")
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

