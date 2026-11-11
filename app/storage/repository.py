"""PostgreSQL Repository for NSE Pulse.

Provides database interaction with SQLAlchemy:
- Automatic schema creation
- Pipeline run and dataset result recording
- Stock record upsert (insert or update on conflict)
- Health check / connection verification
- Optional activation (operates as a no-op if disabled or unreachable)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import Base, DatasetResult, PipelineRun, StockRecord

logger = logging.getLogger("nse_pulse.repository")


class PostgresRepository:
    """Manages persistence to PostgreSQL."""

    def __init__(self, database_url: str, enabled: bool = True) -> None:
        self.database_url = database_url
        self.enabled = enabled
        self._engine = None
        self._session_factory = None

        if self.enabled:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize database engine and verify connectivity."""
        try:
            engine_kwargs = {"pool_pre_ping": True}
            if not self.database_url.startswith("sqlite"):
                engine_kwargs["pool_size"] = 5
                engine_kwargs["max_overflow"] = 10
            self._engine = create_engine(self.database_url, **engine_kwargs)
            self._session_factory = sessionmaker(bind=self._engine)
            # Create tables if not exist
            Base.metadata.create_all(self._engine)
            logger.info("Connected to database and initialized schema.")
        except Exception as exc:
            logger.warning(
                "Could not connect to PostgreSQL at %s: %s. "
                "Database integration will operate in graceful fallback (disabled) mode.",
                self.database_url,
                exc,
            )
            self.enabled = False

    def is_connected(self) -> bool:
        """Check if database connection is alive and healthy."""
        if not self.enabled or self._engine is None:
            return False
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def create_run(self, run_id: str, datasets_attempted: int) -> Optional[PipelineRun]:
        """Record the start of a new pipeline run."""
        if not self.enabled or not self._session_factory:
            return None
        try:
            with self._session_factory() as session:
                run = PipelineRun(
                    id=run_id,
                    started_at=datetime.utcnow(),
                    status="RUNNING",
                    datasets_attempted=datasets_attempted,
                )
                session.add(run)
                session.commit()
                session.refresh(run)
                session.expunge(run)
                return run
        except Exception as exc:
            logger.error("Failed to record pipeline run in DB: %s", exc)
            return None

    def complete_run(
        self,
        run_id: str,
        status: str,
        datasets_succeeded: int,
        datasets_failed: int,
        summary: Dict[str, Any],
    ) -> None:
        """Record the completion of a pipeline run."""
        if not self.enabled or not self._session_factory:
            return
        try:
            with self._session_factory() as session:
                run = session.query(PipelineRun).filter_by(id=run_id).first()
                if run:
                    run.completed_at = datetime.utcnow()
                    run.status = status
                    run.datasets_succeeded = datasets_succeeded
                    run.datasets_failed = datasets_failed
                    run.summary = summary
                    session.commit()
        except Exception as exc:
            logger.error("Failed to complete pipeline run in DB: %s", exc)

    def record_dataset_result(
        self,
        run_id: str,
        dataset_name: str,
        status: str,
        records_fetched: int,
        records_valid: int,
        records_rejected: int,
        duplicates_found: int,
        quality_score: Optional[float],
        processing_seconds: float,
        csv_file_path: Optional[str],
        validation_report: Optional[Dict[str, Any]],
        df: Optional[pd.DataFrame] = None,
    ) -> Optional[str]:
        """Save dataset execution result and stock records."""
        if not self.enabled or not self._session_factory:
            return None
        try:
            with self._session_factory() as session:
                result = DatasetResult(
                    run_id=run_id,
                    dataset_name=dataset_name,
                    status=status,
                    records_fetched=records_fetched,
                    records_valid=records_valid,
                    records_rejected=records_rejected,
                    duplicates_found=duplicates_found,
                    quality_score=quality_score,
                    processing_seconds=processing_seconds,
                    csv_file_path=csv_file_path,
                    validation_report=validation_report,
                )
                session.add(result)
                session.flush()

                # Upsert individual stock records if DataFrame provided
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        trade_date_val = row.get("trade_date")
                        if isinstance(trade_date_val, str):
                            trade_date_obj = datetime.strptime(trade_date_val, "%Y-%m-%d").date()
                        elif isinstance(trade_date_val, datetime):
                            trade_date_obj = trade_date_val.date()
                        else:
                            trade_date_obj = datetime.utcnow().date()

                        stock = StockRecord(
                            dataset_result_id=result.id,
                            dataset_name=dataset_name,
                            symbol=str(row.get("symbol", "")),
                            series=str(row.get("series", "")) if pd.notna(row.get("series")) else None,
                            trade_date=trade_date_obj,
                            ltp=float(row["ltp"]) if pd.notna(row.get("ltp")) else None,
                            pct_change=float(row["pct_change"]) if pd.notna(row.get("pct_change")) else None,
                            traded_qty=float(row["traded_qty"]) if pd.notna(row.get("traded_qty")) else None,
                            raw_data={k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()},
                        )
                        session.merge(stock)

                session.commit()
                return result.id
        except Exception as exc:
            logger.error("Failed to record dataset result in DB: %s", exc)
            return None
