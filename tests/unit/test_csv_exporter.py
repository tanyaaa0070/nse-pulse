"""Unit tests for CSVExportManager and atomic file writing."""

from datetime import date
from pathlib import Path
import pandas as pd
import pytest

from app.storage.csv_exporter import CSVExportManager


def test_csv_file_creation(tmp_path: Path):
    """Test 9: CSV file creation with standardized date-stamped naming."""
    manager = CSVExportManager(output_dir=tmp_path)
    df = pd.DataFrame([{"symbol": "INFY", "ltp": 1500.0, "_is_valid": True}])

    target_date = date(2026, 11, 11)
    file_path = manager.export(
        df=df,
        csv_prefix="top_gainers_losers",
        execution_date=target_date,
    )

    assert file_path.exists()
    assert file_path.name == "top_gainers_losers_2026-11-11.csv"

    # Verify internal flag '_is_valid' was stripped
    saved_df = pd.read_csv(file_path)
    assert "_is_valid" not in saved_df.columns
    assert "symbol" in saved_df.columns
    assert len(saved_df) == 1


def test_repeated_execution_is_safe_and_idempotent(tmp_path: Path):
    """Test 10: Repeated execution for the same trading day safely overwrites without duplication."""
    manager = CSVExportManager(output_dir=tmp_path)
    target_date = date(2026, 11, 11)

    df_first = pd.DataFrame([{"symbol": "INFY", "ltp": 1500.0}])
    path1 = manager.export(df_first, "test_prefix", execution_date=target_date)

    df_second = pd.DataFrame([{"symbol": "INFY", "ltp": 1550.0}, {"symbol": "TCS", "ltp": 3400.0}])
    path2 = manager.export(df_second, "test_prefix", execution_date=target_date)

    assert path1 == path2
    matching_files = list(tmp_path.glob("test_prefix_*.csv"))
    assert len(matching_files) == 1  # Exactly one file exists, no duplicate file clutter

    # Verify latest content is preserved
    final_df = pd.read_csv(path2)
    assert len(final_df) == 2
    assert final_df.iloc[0]["ltp"] == 1550.0

