"""CSV Export Manager with Atomic File Writing.

Ensures reliable, predictable file output:
- Standardized naming: {prefix}_YYYY-MM-DD.csv
- Atomic writing: writes to a temporary file in the target directory and
  replaces atomically via os.replace to prevent partial/corrupted files.
- Safe repeated execution: re-running for the same trading day overwrites
  atomically without downtime or stale partial files.
"""

import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("nse_pulse.csv_exporter")


class CSVExportManager:
    """Manages exporting DataFrames to standardized CSV files with atomic writes."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_filename(self, csv_prefix: str, execution_date: Optional[date] = None) -> str:
        """Generate standardized filename: prefix_YYYY-MM-DD.csv."""
        target_date = execution_date or date.today()
        date_str = target_date.strftime("%Y-%m-%d")
        return f"{csv_prefix}_{date_str}.csv"

    def export(
        self,
        df: pd.DataFrame,
        csv_prefix: str,
        execution_date: Optional[date] = None,
        drop_internal_columns: bool = True,
    ) -> Path:
        """Atomically export a DataFrame to CSV.

        Args:
            df: DataFrame to save.
            csv_prefix: File prefix (e.g. 'top_gainers_losers').
            execution_date: Date for filename stamp (defaults to today).
            drop_internal_columns: If True, strips internal flags like '_is_valid'.

        Returns:
            Path to the written CSV file.

        Raises:
            IOError: If atomic file write fails.
        """
        filename = self.get_filename(csv_prefix, execution_date)
        target_path = self.output_dir / filename

        export_df = df.copy()
        if drop_internal_columns:
            internal_cols = [c for c in export_df.columns if c.startswith("_")]
            if internal_cols:
                export_df = export_df.drop(columns=internal_cols)

        # Atomic write pattern:
        # 1. Create a named temporary file in the SAME directory (same filesystem ensures atomic rename)
        # 2. Write CSV completely and flush to disk
        # 3. Use os.replace() which is atomic on POSIX and Windows (NTFS)
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=self.output_dir,
                delete=False,
                suffix=".tmp",
            ) as tmp:
                temp_file = Path(tmp.name)
                export_df.to_csv(tmp, index=False)
                tmp.flush()
                os.fsync(tmp.fileno())

            # Atomic swap
            os.replace(temp_file, target_path)
            logger.info(
                "Successfully exported %d records atomically to %s",
                len(export_df),
                target_path,
            )
            return target_path

        except Exception as exc:
            # Clean up temp file on failure
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            logger.error("Failed to export CSV atomically to %s: %s", target_path, exc)
            raise IOError(f"Atomic CSV export failed for {target_path}: {exc}") from exc

