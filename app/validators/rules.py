"""Validation rules for market data quality checks.

Each rule is a callable that takes a DataFrame and returns a list of
ValidationIssues. Rules are composable and reusable across datasets.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set

import pandas as pd

from app.validators.models import ValidationIssue, ValidationSeverity

logger = logging.getLogger("nse_pulse.validator.rules")

# Type alias for validation rule functions
ValidationRule = Callable[[pd.DataFrame, str], List[ValidationIssue]]


def check_required_columns(
    df: pd.DataFrame,
    dataset_name: str,
    required_columns: Optional[List[str]] = None,
) -> List[ValidationIssue]:
    """Check that all required columns are present.

    Args:
        df: DataFrame to validate.
        dataset_name: Name of the dataset for context.
        required_columns: List of column names that must exist.

    Returns:
        List of issues for missing columns.
    """
    if required_columns is None:
        return []

    issues = []
    actual_columns = set(df.columns)
    for col in required_columns:
        if col not in actual_columns:
            issues.append(
                ValidationIssue(
                    field=col,
                    rule="required_columns",
                    severity=ValidationSeverity.ERROR,
                    message=f"Required column '{col}' is missing from {dataset_name}",
                )
            )
    return issues


def check_empty_dataset(
    df: pd.DataFrame,
    dataset_name: str,
) -> List[ValidationIssue]:
    """Check if the dataset is empty.

    Returns:
        List with a single warning if the dataset is empty.
    """
    if len(df) == 0:
        return [
            ValidationIssue(
                field="*",
                rule="empty_dataset",
                severity=ValidationSeverity.WARNING,
                message=f"Dataset '{dataset_name}' contains no records",
            )
        ]
    return []


def check_missing_values(
    df: pd.DataFrame,
    dataset_name: str,
    critical_columns: Optional[List[str]] = None,
) -> List[ValidationIssue]:
    """Check for missing/null values in critical columns.

    Args:
        df: DataFrame to validate.
        dataset_name: Name of the dataset.
        critical_columns: Columns where nulls are errors. If None,
            checks 'symbol' by default.

    Returns:
        List of issues for rows with missing values.
    """
    if critical_columns is None:
        critical_columns = ["symbol"]

    issues = []
    for col in critical_columns:
        if col not in df.columns:
            continue
        null_mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
        null_indices = df.index[null_mask].tolist()
        for idx in null_indices:
            issues.append(
                ValidationIssue(
                    field=col,
                    row_index=idx,
                    rule="missing_values",
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing value in critical column '{col}' at row {idx}",
                    value=str(df.at[idx, col]),
                )
            )
    return issues


def check_numeric_validity(
    df: pd.DataFrame,
    dataset_name: str,
    numeric_columns: Optional[List[str]] = None,
) -> List[ValidationIssue]:
    """Check that numeric columns contain valid numbers.

    Args:
        df: DataFrame to validate.
        dataset_name: Name of the dataset.
        numeric_columns: Columns expected to contain numeric values.

    Returns:
        List of issues for invalid numeric values.
    """
    if numeric_columns is None:
        numeric_columns = [
            "ltp", "change", "pct_change", "prev_close",
            "open_price", "high_price", "low_price", "traded_qty",
        ]

    issues = []
    for col in numeric_columns:
        if col not in df.columns:
            continue
        for idx in df.index:
            val = df.at[idx, col]
            if pd.isna(val):
                continue  # Missing values handled by check_missing_values
            try:
                float(val)
            except (ValueError, TypeError):
                issues.append(
                    ValidationIssue(
                        field=col,
                        row_index=idx,
                        rule="numeric_validity",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Invalid numeric value in '{col}' at row {idx}: "
                            f"'{val}' cannot be converted to a number"
                        ),
                        value=str(val),
                    )
                )
    return issues


def check_duplicates(
    df: pd.DataFrame,
    dataset_name: str,
    key_columns: Optional[List[str]] = None,
) -> List[ValidationIssue]:
    """Check for duplicate records based on key columns.

    Args:
        df: DataFrame to validate.
        dataset_name: Name of the dataset.
        key_columns: Columns defining uniqueness. Default: ['symbol'].

    Returns:
        List of issues for duplicate records.
    """
    if key_columns is None:
        key_columns = ["symbol"]

    # Filter to only columns that exist
    existing_keys = [col for col in key_columns if col in df.columns]
    if not existing_keys:
        return []

    issues = []
    duplicated_mask = df.duplicated(subset=existing_keys, keep="first")
    dup_indices = df.index[duplicated_mask].tolist()

    for idx in dup_indices:
        dup_values = {col: str(df.at[idx, col]) for col in existing_keys}
        issues.append(
            ValidationIssue(
                field=",".join(existing_keys),
                row_index=idx,
                rule="duplicate_records",
                severity=ValidationSeverity.WARNING,
                message=(
                    f"Duplicate record at row {idx} in {dataset_name}: "
                    f"{dup_values}"
                ),
                value=str(dup_values),
            )
        )

    return issues


def check_data_types(
    df: pd.DataFrame,
    dataset_name: str,
    type_expectations: Optional[Dict[str, str]] = None,
) -> List[ValidationIssue]:
    """Check that columns conform to expected data types.

    Args:
        df: DataFrame to validate.
        dataset_name: Name of the dataset.
        type_expectations: Map of column → expected type ('numeric', 'string', 'date').

    Returns:
        List of issues for type mismatches.
    """
    if type_expectations is None:
        return []

    issues = []
    for col, expected_type in type_expectations.items():
        if col not in df.columns:
            continue

        if expected_type == "numeric":
            non_numeric = pd.to_numeric(df[col], errors="coerce").isna() & df[col].notna()
            for idx in df.index[non_numeric]:
                issues.append(
                    ValidationIssue(
                        field=col,
                        row_index=idx,
                        rule="data_type_check",
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Expected numeric in '{col}' at row {idx}, "
                            f"got '{df.at[idx, col]}'"
                        ),
                        value=str(df.at[idx, col]),
                    )
                )
    return issues

