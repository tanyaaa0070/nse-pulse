"""Pipeline Health Monitor for NSE Pulse.

Tracks and reports operational health across all datasets:
- Current availability of each dataset
- Timestamp of latest successful execution
- Cumulative failure count and success rate
- Average processing duration
- Validation failure frequencies
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.config.settings import DatasetConfig

logger = logging.getLogger("nse_pulse.health")


class DatasetHealthStatus(BaseModel):
    """Health metrics for an individual dataset."""
    dataset_name: str
    is_healthy: bool
    latest_run_status: str
    latest_successful_run: Optional[str] = None
    total_runs_observed: int = 0
    failure_count: int = 0
    success_rate_pct: float = 100.0
    avg_processing_duration_sec: float = 0.0
    avg_records_retrieved: float = 0.0
    avg_quality_score: float = 0.0


class SystemHealthReport(BaseModel):
    """Overall system health evaluation report."""
    status: str  # HEALTHY, DEGRADED, UNHEALTHY
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    datasets: Dict[str, DatasetHealthStatus] = Field(default_factory=dict)
    total_reports_analyzed: int = 0
    active_issues: List[str] = Field(default_factory=list)


class PipelineHealthMonitor:
    """Calculates health metrics by analyzing persisted JSON execution reports."""

    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = Path(reports_dir)

    def get_system_health(self) -> SystemHealthReport:
        """Inspect stored execution reports and summarize pipeline health."""
        dataset_names = DatasetConfig.get_dataset_names()
        health_by_dataset: Dict[str, Dict[str, Any]] = {
            name: {
                "runs": 0,
                "successes": 0,
                "failures": 0,
                "latest_status": "NEVER_RUN",
                "latest_success": None,
                "durations": [],
                "record_counts": [],
                "quality_scores": [],
            }
            for name in dataset_names
        }

        report_files = sorted(self.reports_dir.glob("run_*.json"), reverse=True)
        recent_reports = report_files[:50]  # Examine last 50 runs

        for rf in recent_reports:
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    datasets_data = data.get("datasets", {})
                    for ds_name, ds_info in datasets_data.items():
                        if ds_name in health_by_dataset:
                            st = health_by_dataset[ds_name]
                            st["runs"] += 1
                            if st["latest_status"] == "NEVER_RUN":
                                st["latest_status"] = ds_info.get("status", "UNKNOWN")

                            if ds_info.get("status") == "SUCCESS":
                                st["successes"] += 1
                                if not st["latest_success"]:
                                    st["latest_success"] = data.get("completed_at")
                            else:
                                st["failures"] += 1

                            st["durations"].append(ds_info.get("processing_duration_seconds", 0.0))
                            st["record_counts"].append(ds_info.get("records_valid", 0))
                            if ds_info.get("quality_score"):
                                st["quality_scores"].append(ds_info.get("quality_score"))
            except Exception as exc:
                logger.debug("Could not parse report %s: %s", rf, exc)

        dataset_statuses: Dict[str, DatasetHealthStatus] = {}
        active_issues: List[str] = []

        for name in dataset_names:
            st = health_by_dataset[name]
            total_runs = st["runs"]
            failures = st["failures"]
            successes = st["successes"]
            rate = (successes / total_runs * 100.0) if total_runs > 0 else 100.0
            avg_dur = (sum(st["durations"]) / total_runs) if total_runs > 0 else 0.0
            avg_rec = (sum(st["record_counts"]) / total_runs) if total_runs > 0 else 0.0
            avg_qs = (sum(st["quality_scores"]) / len(st["quality_scores"])) if st["quality_scores"] else 0.0

            is_healthy = st["latest_status"] == "SUCCESS" or total_runs == 0
            if not is_healthy:
                active_issues.append(f"Dataset '{name}' failed during its latest execution.")

            dataset_statuses[name] = DatasetHealthStatus(
                dataset_name=name,
                is_healthy=is_healthy,
                latest_run_status=st["latest_status"],
                latest_successful_run=st["latest_success"],
                total_runs_observed=total_runs,
                failure_count=failures,
                success_rate_pct=round(rate, 1),
                avg_processing_duration_sec=round(avg_dur, 2),
                avg_records_retrieved=round(avg_rec, 1),
                avg_quality_score=round(avg_qs, 1),
            )

        if not active_issues:
            overall_status = "HEALTHY"
        elif len(active_issues) < len(dataset_names):
            overall_status = "DEGRADED"
        else:
            overall_status = "UNHEALTHY"

        return SystemHealthReport(
            status=overall_status,
            datasets=dataset_statuses,
            total_reports_analyzed=len(recent_reports),
            active_issues=active_issues,
        )

