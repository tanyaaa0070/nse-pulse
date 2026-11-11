"""FastAPI routes for NSE Pulse API."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.schemas import (
    DatasetListResponse,
    DatasetMetadata,
    DownloadTriggerResponse,
    MetricsResponse,
    RunSummaryResponse,
    ValidationSummaryResponse,
)
from app.config.settings import DatasetConfig, Settings, get_settings
from app.monitoring.health import PipelineHealthMonitor
from app.services.orchestrator import PipelineOrchestrator
from app.storage.repository import PostgresRepository

router = APIRouter()


def get_orchestrator(settings: Settings = Depends(get_settings)) -> PipelineOrchestrator:
    return PipelineOrchestrator(settings)


@router.get("/health", summary="Health Check")
def health_check(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Check system and pipeline component health."""
    repo = PostgresRepository(settings.database_url, enabled=settings.db_enabled)
    db_ok = repo.is_connected() if settings.db_enabled else False

    monitor = PipelineHealthMonitor(settings.reports_dir)
    sys_health = monitor.get_system_health()

    return {
        "status": "UP",
        "pipeline_health": sys_health.status,
        "database": "CONNECTED" if db_ok else ("DISABLED" if not settings.db_enabled else "DOWN"),
        "storage_dirs_exist": all(
            p.exists() for p in [settings.output_dir, settings.reports_dir, settings.log_dir]
        ),
        "active_issues": sys_health.active_issues,
    }


@router.get("/datasets", response_model=DatasetListResponse, summary="List Supported Datasets")
def list_datasets() -> DatasetListResponse:
    """List all registered NSE market datasets with metadata."""
    items = []
    for key, cfg in DatasetConfig.DATASETS.items():
        items.append(
            DatasetMetadata(
                name=key,
                display_name=cfg["name"],
                csv_prefix=cfg["csv_prefix"],
                endpoints=cfg["endpoints"],
            )
        )
    return DatasetListResponse(total=len(items), datasets=items)


@router.get("/datasets/{dataset_name}", summary="Get Latest Dataset Records")
def get_dataset(
    dataset_name: str,
    limit: int = Query(50, ge=1, le=500),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Fetch the latest downloaded records for a specific dataset from CSV."""
    cfg = DatasetConfig.get_config(dataset_name)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_name}' not found. Supported: {DatasetConfig.get_dataset_names()}",
        )

    csv_prefix = cfg["csv_prefix"]
    matching_files = sorted(settings.output_dir.glob(f"{csv_prefix}_*.csv"), reverse=True)
    if not matching_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data files found for dataset '{dataset_name}'. Run a download first.",
        )

    latest_file = matching_files[0]
    try:
        df = pd.read_csv(latest_file)
        # Replace NaN with None for valid JSON serialization
        df = df.where(pd.notnull(df), None)
        records = df.head(limit).to_dict(orient="records")
        return {
            "dataset_name": dataset_name,
            "file": latest_file.name,
            "total_records_in_file": len(df),
            "returned_count": len(records),
            "data": records,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading dataset file {latest_file.name}: {exc}",
        )


@router.post("/download/all", summary="Download All 4 Datasets")
def download_all_datasets(
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    """Trigger full pipeline execution across all four datasets with failure isolation."""
    report = orchestrator.run()
    return report.model_dump()


@router.post(
    "/download/{dataset_name}",
    response_model=DownloadTriggerResponse,
    summary="Download Individual Dataset",
)
def download_single_dataset(
    dataset_name: str,
    orchestrator: PipelineOrchestrator = Depends(get_orchestrator),
) -> DownloadTriggerResponse:
    """Trigger on-demand acquisition, validation, and export of a single dataset."""
    cfg = DatasetConfig.get_config(dataset_name)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_name}' not found. Supported: {DatasetConfig.get_dataset_names()}",
        )

    summary, _ = orchestrator.process_dataset(dataset_name)

    if summary.status == "FAILED":
        return DownloadTriggerResponse(
            run_id="on-demand",
            dataset_name=dataset_name,
            status="FAILED",
            message=f"Acquisition failed: {summary.error_message}",
            duration_seconds=summary.processing_duration_seconds,
        )

    return DownloadTriggerResponse(
        run_id="on-demand",
        dataset_name=dataset_name,
        status="SUCCESS",
        message="Dataset retrieved, validated, and stored successfully.",
        records_fetched=summary.records_fetched,
        records_valid=summary.records_valid,
        quality_score=summary.quality_score,
        csv_file_path=summary.csv_file_path,
        duration_seconds=summary.processing_duration_seconds,
    )


@router.get("/runs", response_model=List[RunSummaryResponse], summary="Get Execution History")
def get_runs(
    limit: int = Query(20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> List[RunSummaryResponse]:
    """Retrieve historical pipeline runs from JSON audit reports."""
    report_files = sorted(settings.reports_dir.glob("run_*.json"), reverse=True)[:limit]
    runs = []

    for rf in report_files:
        try:
            with open(rf, "r", encoding="utf-8") as f:
                data = json.load(f)
                runs.append(
                    RunSummaryResponse(
                        run_id=data.get("run_id", "unknown"),
                        started_at=data.get("started_at", ""),
                        completed_at=data.get("completed_at", ""),
                        overall_status=data.get("overall_status", "UNKNOWN"),
                        datasets_attempted=data.get("datasets_attempted", 0),
                        datasets_succeeded=data.get("datasets_succeeded", 0),
                        datasets_failed=data.get("datasets_failed", 0),
                        total_duration_seconds=data.get("total_duration_seconds", 0.0),
                    )
                )
        except Exception:
            continue

    return runs


@router.get(
    "/validation/{dataset_name}",
    response_model=ValidationSummaryResponse,
    summary="Get Latest Validation Report",
)
def get_validation_report(
    dataset_name: str,
    settings: Settings = Depends(get_settings),
) -> ValidationSummaryResponse:
    """Fetch the latest validation summary for a given dataset."""
    cfg = DatasetConfig.get_config(dataset_name)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_name}' not found.",
        )

    report_files = sorted(settings.reports_dir.glob("run_*.json"), reverse=True)
    for rf in report_files:
        try:
            with open(rf, "r", encoding="utf-8") as f:
                data = json.load(f)
                ds_info = data.get("datasets", {}).get(dataset_name)
                if ds_info and "validation_summary" in ds_info:
                    val_sum = ds_info["validation_summary"]
                    return ValidationSummaryResponse(
                        dataset_name=dataset_name,
                        total_records=val_sum.get("total_records", 0),
                        valid_records=val_sum.get("valid_records", 0),
                        rejected_records=val_sum.get("rejected_records", 0),
                        is_valid=val_sum.get("is_valid", True),
                        error_count=val_sum.get("error_count", 0),
                        warning_count=val_sum.get("warning_count", 0),
                        missing_columns=val_sum.get("missing_columns", []),
                        duplicate_count=val_sum.get("duplicate_count", 0),
                        details=val_sum,
                    )
        except Exception:
            continue

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No validation records found for dataset '{dataset_name}'.",
    )


@router.get("/metrics", response_model=MetricsResponse, summary="Pipeline Metrics")
def get_metrics(settings: Settings = Depends(get_settings)) -> MetricsResponse:
    """Retrieve aggregate system metrics and health status."""
    monitor = PipelineHealthMonitor(settings.reports_dir)
    sys_health = monitor.get_system_health()

    repo = PostgresRepository(settings.database_url, enabled=settings.db_enabled)

    return MetricsResponse(
        system_status=sys_health.status,
        total_runs=sys_health.total_reports_analyzed,
        datasets_active=len(sys_health.datasets),
        dataset_health={k: v.model_dump() for k, v in sys_health.datasets.items()},
        database_connected=repo.is_connected() if settings.db_enabled else False,
    )
