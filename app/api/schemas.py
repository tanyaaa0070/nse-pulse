"""Pydantic schemas for FastAPI REST endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetMetadata(BaseModel):
    name: str
    display_name: str
    csv_prefix: str
    endpoints: Dict[str, str]


class DatasetListResponse(BaseModel):
    total: int
    datasets: List[DatasetMetadata]


class DownloadTriggerResponse(BaseModel):
    run_id: str
    dataset_name: Optional[str] = None
    status: str
    message: str
    records_fetched: Optional[int] = None
    records_valid: Optional[int] = None
    quality_score: Optional[float] = None
    csv_file_path: Optional[str] = None
    duration_seconds: Optional[float] = None


class ValidationSummaryResponse(BaseModel):
    dataset_name: str
    total_records: int
    valid_records: int
    rejected_records: int
    is_valid: bool
    error_count: int
    warning_count: int
    missing_columns: List[str]
    duplicate_count: int
    details: Optional[Dict[str, Any]] = None


class MetricsResponse(BaseModel):
    system_status: str
    total_runs: int
    datasets_active: int
    dataset_health: Dict[str, Any]
    database_connected: bool


class RunSummaryResponse(BaseModel):
    run_id: str
    started_at: str
    completed_at: str
    overall_status: str
    datasets_attempted: int
    datasets_succeeded: int
    datasets_failed: int
    total_duration_seconds: float

