"""Data normalization engine for NSE market data.

Cleans and standardizes raw parsed data:
- Strips whitespace and normalizes text casing (e.g. UPPERCASE symbols)
- Cleans numeric strings containing commas, percentage signs, or currency symbols
- Parses diverse date/timestamp formats into standard ISO YYYY-MM-DD
"""

import logging
import re
from datetime import date, datetime
from typing import List, Optional

import pandas as pd

logger = logging.getLogger("nse_pulse.normalizer")


class DataNormalizer:
    """Normalizes DataFrame columns to consistent types and formats."""

    @staticmethod
    def clean_numeric_series(series: pd.Series) -> pd.Series:
        """Convert string series with commas/symbols into clean float series."""
        if series.empty:
            return series

        def _clean_val(val):
            if pd.isna(val) or val is None:
                return None
            if isinstance(val, (int, float)):
                return float(val)
            val_str = str(val).strip().replace(",", "").replace("%", "").replace("₹", "")
            if val_str in ("", "-", "--", "N/A", "NA", "null", "None"):
                return None
            try:
                return float(val_str)
            except (ValueError, TypeError):
                return None

        return series.apply(_clean_val)

    @staticmethod
    def clean_string_series(series: pd.Series, uppercase: bool = False) -> pd.Series:
        """Strip whitespace and optionally uppercase strings."""
        if series.empty:
            return series

        def _clean_str(val):
            if pd.isna(val) or val is None:
                return ""
            s = str(val).strip()
            return s.upper() if uppercase else s

        return series.apply(_clean_str)

    @staticmethod
    def parse_date(date_val: any, fallback_date: Optional[date] = None) -> str:
        """Parse various NSE date representations into ISO YYYY-MM-DD string."""
        if fallback_date is None:
            fallback_date = date.today()

        if pd.isna(date_val) or date_val is None or str(date_val).strip() in ("", "-", "None", "nan"):
            return fallback_date.isoformat()

        date_str = str(date_val).strip()

        # Common NSE date patterns
        date_patterns = [
            "%d-%b-%Y",           # 11-Nov-2026
            "%d-%b-%Y %H:%M:%S",  # 11-Nov-2026 15:30:00
            "%d-%m-%Y",           # 11-11-2026
            "%Y-%m-%d",           # 2026-11-11
            "%Y-%m-%d %H:%M:%S",  # 2026-11-11 15:30:00
            "%d/%m/%Y",           # 11/11/2026
            "%b %d, %Y",          # Nov 11, 2026
        ]

        for pattern in date_patterns:
            try:
                parsed = datetime.strptime(date_str, pattern)
                return parsed.date().isoformat()
            except (ValueError, TypeError):
                continue

        # Regex fallback for embedded dates like "As on 11-Nov-2026"
        match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4})", date_str)
        if match:
            try:
                parsed = datetime.strptime(match.group(1), "%d-%b-%Y")
                return parsed.date().isoformat()
            except (ValueError, TypeError):
                pass

        logger.debug("Could not parse date '%s', using fallback %s", date_str, fallback_date)
        return fallback_date.isoformat()

    def normalize(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        numeric_columns: Optional[List[str]] = None,
        trade_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Run standard normalization pipeline on the DataFrame."""
        if df.empty:
            return df.copy()

        normalized = df.copy()

        # 1. Clean symbols: strip whitespace, uppercase
        if "symbol" in normalized.columns:
            normalized["symbol"] = self.clean_string_series(normalized["symbol"], uppercase=True)

        if "series" in normalized.columns:
            normalized["series"] = self.clean_string_series(normalized["series"], uppercase=True)

        # 2. Normalize numeric columns
        if numeric_columns:
            for col in numeric_columns:
                if col in normalized.columns:
                    normalized[col] = self.clean_numeric_series(normalized[col])

        # 3. Standardize trade_date
        effective_date = trade_date or date.today()
        if "trade_date" in normalized.columns:
            normalized["trade_date"] = normalized["trade_date"].apply(
                lambda d: self.parse_date(d, fallback_date=effective_date)
            )
        else:
            normalized["trade_date"] = effective_date.isoformat()

        logger.debug("Normalized dataset '%s' (%d rows)", dataset_name, len(normalized))
        return normalized

