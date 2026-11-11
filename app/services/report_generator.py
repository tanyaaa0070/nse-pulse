"""JSON Execution Report Generator for NSE Pulse.

Generates comprehensive, machine-readable audit reports for every pipeline execution:
- Run ID and execution timestamps
- Overall pipeline status and dataset-level statuses
- Total record counts, valid records, rejected records
- Validation issues by severity
- Data quality scores and grades
- Errors encountered during execution
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger("nse_pulse.report_generator")


class DatasetExecutionSummary(BaseModel):
    """Summary of a single dataset's processing within a run."""
    dataset_name: str
    status: str  # SUCCESS, FAILED, PARTIAL
    records_fetched: int = 0
    records_valid: int = 0
    records_rejected: int = 0
    duplicates_removed: int = 0
    quality_score: float = 0.0
    quality_grade: str = "N/A"
    processing_duration_seconds: float = 0.0
    csv_file_path: str = ""
    error_message: str = ""
    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    change_detection_summary: Dict[str, Any] = Field(default_factory=dict)


class PipelineExecutionReport(BaseModel):
    """Complete audit report for a pipeline run."""
    run_id: str
    started_at: str
    completed_at: str
    total_duration_seconds: float
    overall_status: str  # SUCCESS, PARTIAL_SUCCESS, FAILED
    datasets_attempted: int
    datasets_succeeded: int
    datasets_failed: int
    datasets: Dict[str, DatasetExecutionSummary] = Field(default_factory=dict)


class ReportGenerator:
    """Creates JSON execution reports alongside exported CSVs."""

    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, report: PipelineExecutionReport) -> Path:
        """Serialize report to disk as JSON."""
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"run_{report.run_id}_{timestamp_str}.json"
        report_path = self.reports_dir / filename

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report.model_dump(), f, indent=2, default=str)
            logger.info("Saved pipeline execution report to %s", report_path)
            return report_path
        except Exception as exc:
            logger.error("Failed to write execution report to %s: %s", report_path, exc)
            raise IOError(f"Could not write execution report: {exc}") from exc

