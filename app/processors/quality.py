"""Data Quality Scoring Engine for NSE Pulse.

Calculates a transparent, weighted Data Quality Score (0 to 100)
based on four objective dimensions:
1. Completeness (Weight: 30%): Proportion of required & critical fields populated without nulls/blanks.
2. Schema Conformity (Weight: 25%): Ratio of expected schema columns actually present in the dataset.
3. Duplicate Health (Weight: 20%): Cleanliness from duplicate records (100% when no duplicates exist).
4. Data Type Validity (Weight: 25%): Proportion of numeric fields that are valid numbers within logical bounds.

Formula:
  Score = (W_comp * S_comp) + (W_conf * S_conf) + (W_dup * S_dup) + (W_type * S_type)

NOTE: This is an internal engineering health metric developed for data reliability
assessment. It is NOT an official metric issued or endorsed by the National Stock Exchange of India.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from pydantic import BaseModel, Field

from app.validators.models import ValidationReport, ValidationSeverity


class QualityDimensionScore(BaseModel):
    """Detailed score breakdown for a specific quality dimension."""
    dimension: str
    weight: float
    raw_score: float = Field(..., ge=0.0, le=100.0)
    weighted_score: float = Field(..., ge=0.0, le=100.0)
    description: str


class DataQualityReport(BaseModel):
    """Complete transparent data quality evaluation report."""
    dataset_name: str
    overall_score: float = Field(..., ge=0.0, le=100.0)
    grade: str  # A (>=90), B (>=80), C (>=70), D (>=60), F (<60)
    dimensions: Dict[str, QualityDimensionScore]
    summary: str
    is_acceptable: bool
    disclaimer: str = (
        "Internal engineering metric designed for pipeline monitoring. "
        "Not an official NSE India quality benchmark."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "overall_score": round(self.overall_score, 2),
            "grade": self.grade,
            "is_acceptable": self.is_acceptable,
            "dimensions": {
                dim: {
                    "weight": d.weight,
                    "raw_score": round(d.raw_score, 2),
                    "weighted_score": round(d.weighted_score, 2),
                    "description": d.description,
                }
                for dim, d in self.dimensions.items()
            },
            "summary": self.summary,
            "disclaimer": self.disclaimer,
        }


class DataQualityScorer:
    """Evaluates data quality using validation outputs and dataset properties."""

    WEIGHTS = {
        "completeness": 0.30,
        "schema_conformity": 0.25,
        "duplicate_health": 0.20,
        "data_type_validity": 0.25,
    }

    def compute_score(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        validation_report: ValidationReport,
        expected_columns: List[str],
    ) -> DataQualityReport:
        """Compute the composite Data Quality Score.

        Args:
            df: The processed DataFrame.
            dataset_name: Dataset name.
            validation_report: Output of the ValidationEngine.
            expected_columns: List of columns expected by the schema.

        Returns:
            DataQualityReport with comprehensive breakdown.
        """
        # If DataFrame is empty
        if df.empty or validation_report.total_records == 0:
            dimensions = {
                "completeness": QualityDimensionScore(
                    dimension="completeness",
                    weight=self.WEIGHTS["completeness"],
                    raw_score=0.0,
                    weighted_score=0.0,
                    description="No records present to evaluate completeness.",
                ),
                "schema_conformity": QualityDimensionScore(
                    dimension="schema_conformity",
                    weight=self.WEIGHTS["schema_conformity"],
                    raw_score=100.0 if not validation_report.missing_columns else 0.0,
                    weighted_score=(
                        self.WEIGHTS["schema_conformity"] * 100.0
                        if not validation_report.missing_columns
                        else 0.0
                    ),
                    description="Schema check on empty dataset.",
                ),
                "duplicate_health": QualityDimensionScore(
                    dimension="duplicate_health",
                    weight=self.WEIGHTS["duplicate_health"],
                    raw_score=100.0,
                    weighted_score=self.WEIGHTS["duplicate_health"] * 100.0,
                    description="Zero duplicates in empty dataset.",
                ),
                "data_type_validity": QualityDimensionScore(
                    dimension="data_type_validity",
                    weight=self.WEIGHTS["data_type_validity"],
                    raw_score=0.0,
                    weighted_score=0.0,
                    description="No records to test data type validity.",
                ),
            }
            overall = sum(d.weighted_score for d in dimensions.values())
            return DataQualityReport(
                dataset_name=dataset_name,
                overall_score=overall,
                grade="F",
                dimensions=dimensions,
                summary="Dataset is empty.",
                is_acceptable=False,
            )

        total_records = len(df)

        # 1. Completeness: ratio of non-null cells across checked columns
        total_cells = total_records * max(1, len(df.columns))
        missing_cells = df.isna().sum().sum()
        completeness_ratio = max(0.0, 1.0 - (missing_cells / total_cells))
        completeness_raw = completeness_ratio * 100.0

        # 2. Schema conformity: ratio of expected columns present
        if expected_columns:
            present_cols = [c for c in expected_columns if c in df.columns]
            conformity_raw = (len(present_cols) / len(expected_columns)) * 100.0
        else:
            conformity_raw = 100.0

        # 3. Duplicate health: 100% minus duplicate percentage
        duplicate_count = validation_report.duplicate_count
        duplicate_ratio = min(1.0, duplicate_count / total_records)
        dup_health_raw = (1.0 - duplicate_ratio) * 100.0

        # 4. Data type validity: proportion of rows without type / numeric errors
        type_errors = sum(
            1
            for issue in validation_report.issues
            if issue.rule in ("numeric_validity", "data_type_check")
            and issue.severity == ValidationSeverity.ERROR
        )
        type_valid_ratio = max(0.0, 1.0 - (type_errors / total_records))
        type_validity_raw = type_valid_ratio * 100.0

        # Calculate weighted composite score
        dimensions = {
            "completeness": QualityDimensionScore(
                dimension="completeness",
                weight=self.WEIGHTS["completeness"],
                raw_score=completeness_raw,
                weighted_score=completeness_raw * self.WEIGHTS["completeness"],
                description=f"{round(completeness_raw, 1)}% of data cells are non-null and populated.",
            ),
            "schema_conformity": QualityDimensionScore(
                dimension="schema_conformity",
                weight=self.WEIGHTS["schema_conformity"],
                raw_score=conformity_raw,
                weighted_score=conformity_raw * self.WEIGHTS["schema_conformity"],
                description=f"{round(conformity_raw, 1)}% of required/expected columns present.",
            ),
            "duplicate_health": QualityDimensionScore(
                dimension="duplicate_health",
                weight=self.WEIGHTS["duplicate_health"],
                raw_score=dup_health_raw,
                weighted_score=dup_health_raw * self.WEIGHTS["duplicate_health"],
                description=f"{duplicate_count} duplicate records detected ({round(dup_health_raw, 1)}% duplicate-free).",
            ),
            "data_type_validity": QualityDimensionScore(
                dimension="data_type_validity",
                weight=self.WEIGHTS["data_type_validity"],
                raw_score=type_validity_raw,
                weighted_score=type_validity_raw * self.WEIGHTS["data_type_validity"],
                description=f"{type_errors} type/numeric violations observed.",
            ),
        }

        overall_score = sum(d.weighted_score for d in dimensions.values())

        # Determine letter grade
        if overall_score >= 90.0:
            grade = "A"
        elif overall_score >= 80.0:
            grade = "B"
        elif overall_score >= 70.0:
            grade = "C"
        elif overall_score >= 60.0:
            grade = "D"
        else:
            grade = "F"

        is_acceptable = overall_score >= 75.0 and validation_report.rejected_records == 0

        summary = (
            f"Overall Quality: {round(overall_score, 1)}/100 (Grade {grade}). "
            f"Evaluated {total_records} records across {len(df.columns)} columns."
        )

        return DataQualityReport(
            dataset_name=dataset_name,
            overall_score=overall_score,
            grade=grade,
            dimensions=dimensions,
            summary=summary,
            is_acceptable=is_acceptable,
        )

