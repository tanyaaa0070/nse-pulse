"""Historical Change Detection Service for NSE Pulse.

Compares current trading-day data with the most recent previous
available trading-day data to uncover market dynamics:
- Newly appearing stocks
- Stocks no longer appearing (dropped)
- Significant price changes or volume spurts
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger("nse_pulse.change_detector")


class ChangeDetectionResult:
    """Summary of historical changes between two trading periods."""

    def __init__(
        self,
        dataset_name: str,
        current_date: str,
        previous_date: Optional[str],
        new_stocks: List[str],
        dropped_stocks: List[str],
        significant_changes: List[Dict[str, Any]],
        has_baseline: bool,
    ) -> None:
        self.dataset_name = dataset_name
        self.current_date = current_date
        self.previous_date = previous_date
        self.new_stocks = new_stocks
        self.dropped_stocks = dropped_stocks
        self.significant_changes = significant_changes
        self.has_baseline = has_baseline

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "has_baseline": self.has_baseline,
            "current_date": self.current_date,
            "previous_date": self.previous_date,
            "new_stocks_count": len(self.new_stocks),
            "new_stocks": self.new_stocks[:10],
            "dropped_stocks_count": len(self.dropped_stocks),
            "dropped_stocks": self.dropped_stocks[:10],
            "significant_changes_count": len(self.significant_changes),
            "significant_changes": self.significant_changes[:10],
        }


class HistoricalChangeDetector:
    """Detects metric and composition shifts across consecutive trading days."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    def find_previous_csv(self, csv_prefix: str, current_csv_path: Path) -> Optional[Path]:
        """Find the most recent earlier CSV file for this dataset."""
        pattern = f"{csv_prefix}_*.csv"
        matching_files = sorted(self.output_dir.glob(pattern))

        # Filter out current file and sort descending
        earlier_files = [
            f for f in matching_files
            if f.resolve() != current_csv_path.resolve() and f.name < current_csv_path.name
        ]
        return earlier_files[-1] if earlier_files else None

    def detect_changes(
        self,
        current_df: pd.DataFrame,
        dataset_name: str,
        csv_prefix: str,
        current_file_path: Path,
        current_date_str: str,
    ) -> ChangeDetectionResult:
        """Compare current DataFrame against the prior trading day's CSV."""
        prev_file = self.find_previous_csv(csv_prefix, current_file_path)

        if prev_file is None or not prev_file.exists():
            logger.info("No prior baseline CSV found for %s. Establishing baseline.", dataset_name)
            return ChangeDetectionResult(
                dataset_name=dataset_name,
                current_date=current_date_str,
                previous_date=None,
                new_stocks=current_df["symbol"].dropna().unique().tolist() if "symbol" in current_df else [],
                dropped_stocks=[],
                significant_changes=[],
                has_baseline=False,
            )

        try:
            prev_df = pd.read_csv(prev_file)
            prev_date_str = prev_file.stem.replace(f"{csv_prefix}_", "")

            curr_symbols = set(current_df["symbol"].dropna().unique()) if "symbol" in current_df else set()
            prev_symbols = set(prev_df["symbol"].dropna().unique()) if "symbol" in prev_df else set()

            new_stocks = sorted(list(curr_symbols - prev_symbols))
            dropped_stocks = sorted(list(prev_symbols - curr_symbols))

            # Metric changes for persisting symbols
            common_symbols = curr_symbols.intersection(prev_symbols)
            significant_changes = []

            if "symbol" in current_df and "symbol" in prev_df:
                c_idx = current_df.set_index("symbol")
                p_idx = prev_df.set_index("symbol")

                for sym in common_symbols:
                    c_row = c_idx.loc[sym]
                    p_row = p_idx.loc[sym]

                    # Handle duplicate symbols safely by taking first row
                    if isinstance(c_row, pd.DataFrame):
                        c_row = c_row.iloc[0]
                    if isinstance(p_row, pd.DataFrame):
                        p_row = p_row.iloc[0]

                    # Compare LTP if available
                    if "ltp" in c_row and "ltp" in p_row and pd.notna(c_row["ltp"]) and pd.notna(p_row["ltp"]):
                        c_ltp = float(c_row["ltp"])
                        p_ltp = float(p_row["ltp"])
                        if p_ltp > 0:
                            diff_pct = ((c_ltp - p_ltp) / p_ltp) * 100.0
                            if abs(diff_pct) >= 5.0:  # >= 5% change considered notable
                                significant_changes.append({
                                    "symbol": sym,
                                    "metric": "ltp",
                                    "previous": p_ltp,
                                    "current": c_ltp,
                                    "change_pct": round(diff_pct, 2),
                                })

            logger.info(
                "Change detection for %s vs %s: %d new, %d dropped, %d significant shifts",
                dataset_name,
                prev_date_str,
                len(new_stocks),
                len(dropped_stocks),
                len(significant_changes),
            )

            return ChangeDetectionResult(
                dataset_name=dataset_name,
                current_date=current_date_str,
                previous_date=prev_date_str,
                new_stocks=new_stocks,
                dropped_stocks=dropped_stocks,
                significant_changes=significant_changes,
                has_baseline=True,
            )

        except Exception as exc:
            logger.warning("Error running change detection for %s: %s", dataset_name, exc)
            return ChangeDetectionResult(
                dataset_name=dataset_name,
                current_date=current_date_str,
                previous_date=None,
                new_stocks=[],
                dropped_stocks=[],
                significant_changes=[],
                has_baseline=False,
            )

