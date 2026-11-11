"""Unit tests for ValidationEngine and rules."""

import pandas as pd
from app.validators.engine import ValidationEngine
from app.validators.models import ValidationSeverity


def test_missing_expected_columns():
    """Test 6: Flagging missing required columns in schema."""
    engine = ValidationEngine()
    df = pd.DataFrame([{"ltp": 100.0, "pct_change": 2.5}])  # Missing 'symbol'

    _, report = engine.validate(df, "top-gainers-losers")

    assert not report.is_valid
    assert "symbol" in report.missing_columns
    assert any(i.rule == "required_columns" and i.field == "symbol" for i in report.issues)


def test_empty_dataset_validation():
    """Test 5: Empty dataset produces warning issue and zero valid records."""
    engine = ValidationEngine()
    df = pd.DataFrame(columns=["symbol", "ltp", "pct_change", "category"])

    _, report = engine.validate(df, "top-gainers-losers")

    assert report.total_records == 0
    assert any(i.rule == "empty_dataset" and i.severity == ValidationSeverity.WARNING for i in report.issues)


def test_duplicate_records_detection():
    """Test 7: Detecting duplicate stock entries."""
    engine = ValidationEngine()
    df = pd.DataFrame([
        {"symbol": "INFY", "category": "gainer", "ltp": 1500.0, "pct_change": 3.0},
        {"symbol": "INFY", "category": "gainer", "ltp": 1500.0, "pct_change": 3.0},  # Duplicate
        {"symbol": "TCS", "category": "gainer", "ltp": 3400.0, "pct_change": 2.0},
    ])

    _, report = engine.validate(df, "top-gainers-losers")

    assert report.duplicate_count == 1
    assert any(i.rule == "duplicate_records" for i in report.issues)


def test_invalid_numeric_values():
    """Test 8: Detecting non-numeric strings in numeric columns."""
    engine = ValidationEngine()
    df = pd.DataFrame([
        {"symbol": "INFY", "category": "gainer", "ltp": "NOT_A_NUMBER", "pct_change": 3.0},
        {"symbol": "TCS", "category": "gainer", "ltp": 3400.0, "pct_change": 2.0},
    ])

    validated_df, report = engine.validate(df, "top-gainers-losers")

    assert any(i.rule == "numeric_validity" and i.field == "ltp" for i in report.issues)
    assert report.rejected_records == 1
    assert report.valid_records == 1
    # Verify row is marked _is_valid=False rather than dropped silently
    assert len(validated_df) == 2
    assert not validated_df.loc[0, "_is_valid"]
    assert validated_df.loc[1, "_is_valid"]

