"""Parser for Top Gainers & Losers dataset.

Transforms the raw NSE gainers/losers API response into a unified
DataFrame with a 'category' column distinguishing gainers from losers.
"""

from typing import Any, Dict

import pandas as pd

from app.parsers.base import BaseParser


class TopGainersLosersParser(BaseParser):
    """Parses top gainers and losers data into a unified DataFrame."""

    # Expected columns from the NSE API response
    EXPECTED_COLUMNS = [
        "symbol", "series", "open_price", "high_price", "low_price",
        "ltp", "prev_close", "change", "pct_change", "traded_qty",
        "trade_date", "category",
    ]

    # Mapping from NSE API field names to our standardized names
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
        super().__init__(name="top-gainers-losers")

    def parse(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """Parse gainers and losers into a single DataFrame.

        Args:
            raw_data: Dict with 'gainers' and 'losers' sub-responses.

        Returns:
            DataFrame with all records and a 'category' column.
        """
        all_records = []

        for category_key, category_label in [
            ("gainers", "gainer"),
            ("losers", "loser"),
        ]:
            sub_data = raw_data.get(category_key, {})
            records = self._extract_records(sub_data)
            self.logger.info(
                "Parsed %d %s records",
                len(records),
                category_label,
            )
            for record in records:
                record["_category"] = category_label
            all_records.extend(records)

        if not all_records:
            self.logger.warning("No records found in gainers/losers response")
            return pd.DataFrame(columns=self.EXPECTED_COLUMNS)

        df = pd.DataFrame(all_records)
        df = self._rename_columns(df)
        if "_category" in df.columns:
            df["category"] = df.pop("_category")
        elif "category" not in df.columns:
            df["category"] = "unknown"

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

