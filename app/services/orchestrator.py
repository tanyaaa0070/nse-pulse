"""Pipeline Orchestrator for NSE Pulse.

Coordinates the end-to-end data pipeline:
Acquisition → Response Handling → Parsing → Normalization → Validation
→ Deduplication → Quality Scoring → CSV Storage → DB Storage → Change Detection
→ Audit Reporting.

Guarantees dataset-level failure isolation: an exception in one dataset
will never abort the remaining datasets.
"""

import logging
import time
import uuid
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.collectors.base import BaseCollector
from app.collectors.nse_client import NSEClient
from app.collectors.top_gainers_losers import TopGainersLosersCollector
from app.collectors.upper_band_hitters import UpperBandHittersCollector
from app.collectors.volume_gainers import VolumeGainersCollector
from app.collectors.week52_high import Week52HighCollector
from app.config.settings import DatasetConfig, Settings
from app.parsers.base import BaseParser
from app.parsers.top_gainers_losers import TopGainersLosersParser
from app.parsers.upper_band_hitters import UpperBandHittersParser
from app.parsers.volume_gainers import VolumeGainersParser
from app.parsers.week52_high import Week52HighParser
from app.processors.deduplicator import DuplicateDetector
from app.processors.normalizer import DataNormalizer
from app.processors.quality import DataQualityScorer
from app.services.change_detector import HistoricalChangeDetector
from app.services.report_generator import (
    DatasetExecutionSummary,
    PipelineExecutionReport,
    ReportGenerator,
)
from app.storage.csv_exporter import CSVExportManager
from app.storage.repository import PostgresRepository
from app.validators.engine import ValidationEngine

logger = logging.getLogger("nse_pulse.orchestrator")


class PipelineOrchestrator:
    """Coordinates pipeline execution across datasets with strict failure isolation."""

    def __init__(
        self,
        settings: Settings,
        client: Optional[NSEClient] = None,
        repository: Optional[PostgresRepository] = None,
    ) -> None:
        self.settings = settings
        self.settings.ensure_directories()

        self.client = client or NSEClient(self.settings)
        self.repository = repository or PostgresRepository(
            database_url=self.settings.database_url,
            enabled=self.settings.db_enabled,
        )

        self.normalizer = DataNormalizer()
        self.validator = ValidationEngine()
        self.deduplicator = DuplicateDetector()
        self.quality_scorer = DataQualityScorer()
        self.csv_exporter = CSVExportManager(self.settings.output_dir)
        self.change_detector = HistoricalChangeDetector(self.settings.output_dir)
        self.report_generator = ReportGenerator(self.settings.reports_dir)

        # Register collectors and parsers
        self._collectors: Dict[str, BaseCollector] = {
            "top-gainers-losers": TopGainersLosersCollector(self.client),
            "upper-band-hitters": UpperBandHittersCollector(self.client),
            "volume-gainers-spurts": VolumeGainersCollector(self.client),
            "52-week-high-equity": Week52HighCollector(self.client),
        }

        self._parsers: Dict[str, BaseParser] = {
            "top-gainers-losers": TopGainersLosersParser(),
            "upper-band-hitters": UpperBandHittersParser(),
            "volume-gainers-spurts": VolumeGainersParser(),
            "52-week-high-equity": Week52HighParser(),
        }

    def process_dataset(
        self,
        dataset_name: str,
        execution_date: Optional[date] = None,
        run_id: Optional[str] = None,
    ) -> Tuple[DatasetExecutionSummary, Optional[pd.DataFrame]]:
        """Process a single dataset through all stages of the pipeline.

        Wrapped in strict exception handling to isolate failure.
        """
        start_time = time.time()
        effective_date = execution_date or date.today()
        summary = DatasetExecutionSummary(dataset_name=dataset_name, status="RUNNING")

        cfg = DatasetConfig.get_config(dataset_name)
        if not cfg:
            summary.status = "FAILED"
            summary.error_message = f"Unknown dataset configuration: {dataset_name}"
            summary.processing_duration_seconds = time.time() - start_time
            return summary, None

        collector = self._collectors.get(dataset_name)
        parser = self._parsers.get(dataset_name)

        if not collector or not parser:
            summary.status = "FAILED"
            summary.error_message = f"Collector or parser not found for {dataset_name}"
            summary.processing_duration_seconds = time.time() - start_time
            return summary, None

        try:
            logger.info(">>> Starting pipeline for dataset: %s", dataset_name)

            # 1. Acquisition
            raw_data = collector.fetch()

            # 2. Parsing
            parsed_df = parser.parse(raw_data)
            summary.records_fetched = len(parsed_df)

            # 3. Normalization
            schema_info = self.validator.DATASET_SCHEMAS.get(dataset_name, {})
            normalized_df = self.normalizer.normalize(
                df=parsed_df,
                dataset_name=dataset_name,
                numeric_columns=schema_info.get("numeric"),
                trade_date=effective_date,
            )

            # 4. Validation
            validated_df, validation_report = self.validator.validate(
                df=normalized_df,
                dataset_name=dataset_name,
            )
            summary.records_valid = validation_report.valid_records
            summary.records_rejected = validation_report.rejected_records
            summary.validation_summary = validation_report.summary()

            # 5. Deduplication
            key_cols = schema_info.get("key", ["symbol"])
            deduped_df, dedup_report = self.deduplicator.deduplicate(
                df=validated_df,
                dataset_name=dataset_name,
                key_columns=key_cols,
            )
            summary.duplicates_removed = dedup_report.duplicate_count

            # 6. Quality Scoring
            expected_cols = schema_info.get("required", [])
            quality_report = self.quality_scorer.compute_score(
                df=deduped_df,
                dataset_name=dataset_name,
                validation_report=validation_report,
                expected_columns=expected_cols,
            )
            summary.quality_score = quality_report.overall_score
            summary.quality_grade = quality_report.grade

            # 7. CSV Storage (Atomic)
            csv_prefix = cfg.get("csv_prefix", dataset_name.replace("-", "_"))
            exported_path = self.csv_exporter.export(
                df=deduped_df,
                csv_prefix=csv_prefix,
                execution_date=effective_date,
            )
            summary.csv_file_path = str(exported_path)

            # 8. Historical Change Detection
            change_result = self.change_detector.detect_changes(
                current_df=deduped_df,
                dataset_name=dataset_name,
                csv_prefix=csv_prefix,
                current_file_path=exported_path,
                current_date_str=effective_date.isoformat(),
            )
            summary.change_detection_summary = change_result.to_dict()

            # 9. Database Storage (Optional)
            if self.repository.enabled and run_id:
                self.repository.record_dataset_result(
                    run_id=run_id,
                    dataset_name=dataset_name,
                    status="SUCCESS",
                    records_fetched=summary.records_fetched,
                    records_valid=summary.records_valid,
                    records_rejected=summary.records_rejected,
                    duplicates_found=summary.duplicates_removed,
                    quality_score=summary.quality_score,
                    processing_seconds=time.time() - start_time,
                    csv_file_path=str(exported_path),
                    validation_report=summary.validation_summary,
                    df=deduped_df,
                )

            summary.status = "SUCCESS"
            summary.processing_duration_seconds = round(time.time() - start_time, 2)
            logger.info(
                "<<< Finished pipeline for %s: SUCCESS (%d valid records, score: %.1f)",
                dataset_name,
                summary.records_valid,
                summary.quality_score,
            )
            return summary, deduped_df

        except Exception as exc:
            summary.status = "FAILED"
            summary.error_message = str(exc)
            summary.processing_duration_seconds = round(time.time() - start_time, 2)
            logger.error("Pipeline failure for dataset %s: %s", dataset_name, exc, exc_info=True)
            return summary, None

    def run(
        self,
        dataset_names: Optional[List[str]] = None,
        execution_date: Optional[date] = None,
    ) -> PipelineExecutionReport:
        """Run the pipeline for specified datasets or all registered datasets.

        Executes each dataset with failure isolation, creates an execution summary,
        generates a JSON audit report, and records metadata to the database.
        """
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()
        effective_date = execution_date or date.today()

        if dataset_names is None:
            dataset_names = DatasetConfig.get_dataset_names()

        logger.info(
            "============================================================"
        )
        logger.info(
            "Starting NSE Pulse Pipeline [Run ID: %s] for %d dataset(s)",
            run_id,
            len(dataset_names),
        )
        logger.info(
            "============================================================"
        )

        # Record in DB if active
        if self.repository.enabled:
            self.repository.create_run(run_id=run_id, datasets_attempted=len(dataset_names))

        dataset_summaries: Dict[str, DatasetExecutionSummary] = {}
        succeeded_count = 0
        failed_count = 0

        for name in dataset_names:
            summary, _ = self.process_dataset(
                dataset_name=name,
                execution_date=effective_date,
                run_id=run_id,
            )
            dataset_summaries[name] = summary
            if summary.status == "SUCCESS":
                succeeded_count += 1
            else:
                failed_count += 1

        completed_at = datetime.utcnow()
        total_duration = round((completed_at - started_at).total_seconds(), 2)

        if failed_count == 0:
            overall_status = "SUCCESS"
        elif succeeded_count > 0:
            overall_status = "PARTIAL_SUCCESS"
        else:
            overall_status = "FAILED"

        report = PipelineExecutionReport(
            run_id=run_id,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            total_duration_seconds=total_duration,
            overall_status=overall_status,
            datasets_attempted=len(dataset_names),
            datasets_succeeded=succeeded_count,
            datasets_failed=failed_count,
            datasets=dataset_summaries,
        )

        # Write audit report JSON
        try:
            self.report_generator.generate_report(report)
        except Exception as exc:
            logger.warning("Could not persist JSON audit report: %s", exc)

        # Complete DB run if active
        if self.repository.enabled:
            self.repository.complete_run(
                run_id=run_id,
                status=overall_status,
                datasets_succeeded=succeeded_count,
                datasets_failed=failed_count,
                summary=report.model_dump(),
            )

        logger.info(
            "============================================================"
        )
        logger.info(
            "NSE Pulse Execution Summary: %s (%d succeeded, %d failed) in %.2fs",
            overall_status,
            succeeded_count,
            failed_count,
            total_duration,
        )
        logger.info(
            "============================================================"
        )

        return report

