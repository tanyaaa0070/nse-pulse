"""SQLAlchemy ORM models for optional PostgreSQL storage.

Defines schemas for:
- pipeline_runs: High-level execution runs
- dataset_results: Per-dataset results, validation summaries, and quality metrics
- stock_records: Individual stock data records with unique constraints
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PipelineRun(Base):
    """Represents a single pipeline execution batch."""
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="RUNNING", nullable=False)  # RUNNING, SUCCESS, PARTIAL_SUCCESS, FAILED
    datasets_attempted = Column(Integer, default=0)
    datasets_succeeded = Column(Integer, default=0)
    datasets_failed = Column(Integer, default=0)
    summary = Column(JSON, nullable=True)

    results = relationship("DatasetResult", back_populates="run", cascade="all, delete-orphan")


class DatasetResult(Base):
    """Represents the processing outcome of a single dataset within a run."""
    __tablename__ = "dataset_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("pipeline_runs.id"), nullable=False)
    dataset_name = Column(String(64), nullable=False)
    status = Column(String(32), default="SUCCESS", nullable=False)
    records_fetched = Column(Integer, default=0)
    records_valid = Column(Integer, default=0)
    records_rejected = Column(Integer, default=0)
    duplicates_found = Column(Integer, default=0)
    quality_score = Column(Float, nullable=True)
    processing_seconds = Column(Float, default=0.0)
    csv_file_path = Column(String(256), nullable=True)
    validation_report = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    run = relationship("PipelineRun", back_populates="results")
    stocks = relationship("StockRecord", back_populates="dataset_result", cascade="all, delete-orphan")


class StockRecord(Base):
    """Represents an individual stock market data record.

    Includes a unique constraint on (dataset_name, symbol, trade_date)
    to prevent duplicate historical entries.
    """
    __tablename__ = "stock_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_result_id = Column(String(36), ForeignKey("dataset_results.id"), nullable=False)
    dataset_name = Column(String(64), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    series = Column(String(16), nullable=True)
    trade_date = Column(Date, nullable=False, index=True)
    ltp = Column(Float, nullable=True)
    pct_change = Column(Float, nullable=True)
    traded_qty = Column(Float, nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset_result = relationship("DatasetResult", back_populates="stocks")

    __table_args__ = (
        UniqueConstraint("dataset_name", "symbol", "trade_date", name="uq_stock_record_per_date"),
    )

