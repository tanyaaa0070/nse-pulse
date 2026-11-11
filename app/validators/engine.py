"""Data validation engine that orchestrates rule execution.

The engine runs a configurable set of validation rules against
a DataFrame and produces a comprehensive ValidationReport.
Invalid records are flagged but never silently discarded.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from app.validators.models import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from app.validators.rules import (
    check_data_types,
    check_duplicates,
    check_empty_dataset,
    check_missing_values,
    check_numeric_validity,
    check_required_columns,
)

logger = logging.getLogger("nse_pulse.validator.engine")


class ValidationEngine:
    """Orchestrates data validation across multiple rules.

    The engine is configured per-dataset with expected columns,
    critical fields, and numeric columns. It runs all applicable
    rules and collects results into a ValidationReport.

    Invalid records are marked (not dropped) so downstream consumers
    can decide how to handle them.
    """

    # Default column expectations per dataset
    DATASET_SCHEMAS: Dict[str, Dict[str, List[str]]] = {
        "top-gainers-losers": {
            "required": ["symbol", "ltp", "pct_change", "category"],
            "critical": ["symbol"],
            "numeric": [
                "open_price", "high_price", "low_price", "ltp",
                "prev_close", "change", "pct_change", "traded_qty",
            ],
            "key": ["symbol", "category"],
        },
        "upper-band-hitters": {
            "required": ["symbol", "ltp", "pct_change"],
            "critical": ["symbol"],
            "numeric": [
                "open_price", "high_price", "low_price", "ltp",
                "prev_close", "change", "pct_change", "traded_qty",
            ],
            "key": ["symbol"],
        },
        "volume-gainers-spurts": {
            "required": ["symbol", "ltp"],
            "critical": ["symbol"],
            "numeric": [
                "ltp", "change", "pct_change", "prev_close",
                "traded_qty",
            ],
            "key": ["symbol"],
        },
        "52-week-high-equity": {
            "required": ["symbol", "ltp"],
            "critical": ["symbol"],
            "numeric": [
                "ltp", "change", "pct_change", "prev_close",
                "high_52_week", "low_52_week", "traded_qty",
            ],
            "key": ["symbol"],
        },
    }

    def validate(
        self,
        df: pd.DataFrame,
        dataset_name: str,
    ) -> Tuple[pd.DataFrame, ValidationReport]:
        """Run all validation rules against a DataFrame.

        Args:
            df: DataFrame to validate.
            dataset_name: Name of the dataset (used to look up schema).

        Returns:
            Tuple of (cleaned DataFrame with '_is_valid' column, ValidationReport).
            Invalid records have _is_valid=False but are NOT removed.
        """
        report = ValidationReport(
            dataset_name=dataset_name,
            total_records=len(df),
        )

        schema = self.DATASET_SCHEMAS.get(dataset_name, {})

        # Track which columns were checked
        report.columns_checked = list(df.columns)

        # Check required columns
        required = schema.get("required", [])
        if required:
            issues = check_required_columns(df, dataset_name, required)
            for issue in issues:
                report.add_issue(issue)
            report.missing_columns = [
                col for col in required if col not in df.columns
            ]

        # Check for extra columns
        expected_all = set(required)
        report.extra_columns = [
            col for col in df.columns if col not in expected_all and col != "_is_valid"
        ]

        # Check for empty dataset
        issues = check_empty_dataset(df, dataset_name)
        for issue in issues:
            report.add_issue(issue)

        if len(df) == 0:
            report.valid_records = 0
            report.rejected_records = 0
            return df, report

        # Check missing values in critical columns
        critical = schema.get("critical", ["symbol"])
        issues = check_missing_values(df, dataset_name, critical)
        for issue in issues:
            report.add_issue(issue)

        # Check numeric validity
        numeric = schema.get("numeric", [])
        issues = check_numeric_validity(df, dataset_name, numeric)
        for issue in issues:
            report.add_issue(issue)

        # Check duplicates
        key_cols = schema.get("key", ["symbol"])
        issues = check_duplicates(df, dataset_name, key_cols)
        for issue in issues:
            report.add_issue(issue)
        report.duplicate_count = len(
            [i for i in issues if i.rule == "duplicate_records"]
        )

        # Mark invalid rows
        invalid_rows: Set[int] = set()
        for issue in report.issues:
            if (
                issue.severity == ValidationSeverity.ERROR
                and issue.row_index is not None
            ):
                invalid_rows.add(issue.row_index)

        df = df.copy()
        df["_is_valid"] = True
        df.loc[list(invalid_rows), "_is_valid"] = False

        report.valid_records = int(df["_is_valid"].sum())
        report.rejected_records = report.total_records - report.valid_records

        logger.info(
            "Validation complete for '%s': %d/%d valid, %d issues",
            dataset_name,
            report.valid_records,
            report.total_records,
            len(report.issues),
            extra={
                "dataset": dataset_name,
                "records_valid": report.valid_records,
                "records_rejected": report.rejected_records,
            },
        )

        return df, report

