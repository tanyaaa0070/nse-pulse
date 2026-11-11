# NSE Pulse – Intelligent Market Data Engineering Platform

> **Reliable Market Data. Validated Pipelines. Actionable Insights.**

[![CI/CD Status](https://github.com/nse-pulse/nse-pulse/actions/workflows/ci.yml/badge.svg)](https://github.com/nse-pulse/nse-pulse/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Coverage](https://img.shields.io/badge/coverage-78%25-brightgreen.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Project Overview

**NSE Pulse** is an enterprise-grade market data engineering platform developed in Python. It automatically acquires, validates, normalizes, deduplicates, and stores four mission-critical equity datasets from the official National Stock Exchange of India (NSE India) website:

1. **Top Gainers & Losers**: `https://www.nseindia.com/market-data/top-gainers-losers`
2. **Upper Band Hitters**: `https://www.nseindia.com/market-data/upper-band-hitters`
3. **Volume Gainers / Spurts**: `https://www.nseindia.com/market-data/volume-gainers-spurts`
4. **52-Week High – Equity Market**: `https://www.nseindia.com/market-data/52-week-high-equity-market`

The platform goes significantly beyond a naive scraping script by implementing an asynchronous, fault-isolated architecture with atomic CSV exports, a transparent 4-dimension data quality scoring framework, optional PostgreSQL persistence, historical change detection across trading sessions, an automated scheduler, and a RESTful API with an interactive monitoring dashboard.

---

## 2. Problem Statement

Algorithmic trading systems, quantitative research desks, and financial analytics platforms require deterministic, high-integrity market data inputs. However, public exchange websites present substantial engineering hurdles:
- **Session-bound internal endpoints**: API endpoints require dynamic session cookie handshakes from the exchange homepage.
- **Access controls & rate throttling**: Excessive concurrent requests trigger HTTP 429 (Too Many Requests) or HTTP 403 (Forbidden) responses.
- **Schema & format volatility**: Unannounced changes in response hierarchies, nested keys, or field naming conventions can break downstream consumers.
- **Data corruption risks**: Process crashes during file export can leave truncated, partial, or malformed data files.
- **Cascading failures**: In monolithic ingestion jobs, a transient failure in one dataset aborts the ingestion of all other datasets.

---

## 3. Objectives

- **Reliability First**: Implement strict dataset-level failure isolation. An error or rate limit on one dataset must never abort processing for the remaining three.
- **Data Quality & Integrity**: Provide a rule-based validation engine that inspects schema conformity, missing critical fields, numeric boundaries, and duplicates without silently discarding invalid records.
- **Predictable Storage**: Guarantee atomic file operations via temp-file staging and `os.replace` to prevent corrupted outputs, using standard `{prefix}_YYYY-MM-DD.csv` naming.
- **Production Automation**: Enable simple CLI invocation (`python main.py`, `--dataset`, `--all`), scheduled background execution, and a containerized FastAPI microservice.
- **Engineering Excellence**: Maintain 100% test passing across unit and integration tests with deterministic mocks, strict PEP 8 compliance, comprehensive type hints, and complete documentation.

---

## 4. System Architecture

NSE Pulse follows a decoupled, pipeline-oriented architecture:

```mermaid
flowchart TD
    subgraph TriggerLayer [Trigger & Orchestration Layer]
        CLI["CLI Entrypoint<br/>(main.py)"]
        API["FastAPI REST Server<br/>(app/api)"]
        SCHED["Pipeline Scheduler<br/>(app/scheduler)"]
    end

    subgraph CoreEngine [Pipeline Coordinator - Orchestrator]
        ORCH["PipelineOrchestrator<br/>(app/services/orchestrator.py)"]
    end

    subgraph IngestionLayer [Data Acquisition & Parsing]
        CLIENT["NSEClient<br/>(Session & Rate Limiter)"]
        COLL["Dataset Collectors<br/>(Gainers, Upper Band, Volume, 52Wk)"]
        PARSE["Dataset Parsers<br/>(JSON to DataFrame Adapters)"]
    end

    subgraph ProcessingLayer [Data Quality & Transformation]
        NORM["DataNormalizer<br/>(Casing, Types, ISO Dates)"]
        VAL["ValidationEngine<br/>(Rule-based Verification)"]
        DEDUP["DuplicateDetector<br/>(Deterministic Hash Deduplication)"]
        SCORER["DataQualityScorer<br/>(4-Dimension Quality Metric)"]
    end

    subgraph StorageLayer [Persistence & Auditing]
        CSV["CSVExportManager<br/>(Atomic OS File Staging)"]
        DB["PostgresRepository<br/>(SQLAlchemy Upsert & Runs)"]
        CHANGE["HistoricalChangeDetector<br/>(Cross-Session Drift Detection)"]
        AUDIT["ReportGenerator<br/>(JSON Execution Reports)"]
    end

    CLI --> ORCH
    API --> ORCH
    SCHED --> ORCH

    ORCH --> CLIENT
    CLIENT --> COLL
    COLL --> PARSE
    PARSE --> NORM
    NORM --> VAL
    VAL --> DEDUP
    DEDUP --> SCORER

    SCORER --> CSV
    SCORER --> DB
    SCORER --> CHANGE
    SCORER --> AUDIT

    style CLI fill:#2563eb,color:#fff
    style API fill:#0891b2,color:#fff
    style ORCH fill:#7c3aed,color:#fff
    style VAL fill:#e11d48,color:#fff
    style CSV fill:#059669,color:#fff
    style DB fill:#d97706,color:#fff
```

### Data Flow Execution Sequence
```mermaid
sequenceDiagram
    autonumber
    actor User as User / Scheduler / API
    participant Orch as Orchestrator
    participant Client as NSEClient
    participant Parser as DatasetParser
    participant Validator as ValidationEngine
    participant Storage as CSVExporter
    participant Audit as ReportGenerator

    User->>Orch: run(dataset_names)
    loop For each dataset in parallel/isolated
        Orch->>Client: get(endpoint)
        Note over Client: Enforces Rate Limit & Session Cookies
        Client-->>Orch: Raw JSON Response
        Orch->>Parser: parse(raw_json)
        Parser-->>Orch: Standardized DataFrame
        Orch->>Validator: validate(dataframe)
        Validator-->>Orch: Validated DF + ValidationReport
        Orch->>Storage: export(clean_df, prefix, date)
        Note over Storage: Atomic write to .tmp -> os.replace()
        Storage-->>Orch: Final CSV Path
    end
    Orch->>Audit: generate_report(run_summary)
    Audit-->>User: Execution Report & Exit Code
```

---

## 5. Technology Stack

| Layer | Technology | Purpose & Value Justification |
|---|---|---|
| **Language** | Python 3.11+ | Modern type annotations, performance optimizations, robust ecosystem. |
| **HTTP Client** | `requests` | Battle-tested session management, cookie persistence, connection pooling. |
| **Data Processing** | `pandas` (v2.1+) | High-throughput columnar transformations, vectorized normalization, deduplication. |
| **Validation & Schema** | `pydantic` (v2.5+) | Type-safe configuration models and validation issue structures. |
| **Configuration** | `pydantic-settings` | 12-factor configuration via `.env` and environment variables. |
| **Web & API** | `fastapi` & `uvicorn` | High-performance asynchronous REST microservice with auto-generated OpenAPI documentation. |
| **Database ORM** | `SQLAlchemy` (v2.0+) | Normalized schema management, transaction boundaries, and optional PostgreSQL persistence. |
| **Scheduler** | `APScheduler` | Thread-safe, background periodic task scheduling with cron and interval triggers. |
| **Testing** | `pytest`, `pytest-cov` | Unit and integration test suite with isolated fixtures and mock HTTP transports. |
| **Containerization** | `Docker` & `docker-compose` | Multi-stage production container build with health checks and PostgreSQL service. |

---

## 6. Project Directory Structure

```
E:\NSE\
├── app/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Pydantic Settings & dataset registry
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseCollector abstract base class
│   │   ├── nse_client.py        # Session & rate-limited HTTP client
│   │   ├── top_gainers_losers.py
│   │   ├── upper_band_hitters.py
│   │   ├── volume_gainers.py
│   │   └── week52_high.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseParser abstract base class
│   │   ├── top_gainers_losers.py
│   │   ├── upper_band_hitters.py
│   │   ├── volume_gainers.py
│   │   └── week52_high.py
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── engine.py            # Core validation orchestrator
│   │   ├── models.py            # ValidationIssue & ValidationReport
│   │   └── rules.py             # Composable validation rules
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── normalizer.py        # Data normalization (types, dates, casing)
│   │   ├── deduplicator.py      # Hash-based duplicate detection service
│   │   └── quality.py           # Data Quality Scoring Engine (0-100)
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── csv_exporter.py      # Atomic file writing & naming manager
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── repository.py        # PostgreSQL repository with fallback
│   ├── services/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # Pipeline coordinator with failure isolation
│   │   ├── change_detector.py   # Historical trading-day change detector
│   │   └── report_generator.py  # JSON audit report generator
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI factory & interactive dashboard
│   │   ├── routes.py            # REST endpoints
│   │   └── schemas.py           # API request/response schemas
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── health.py            # Pipeline health monitor
│   │   └── logging_config.py    # Structured JSON & console logger
│   └── scheduler/
│       ├── __init__.py
│       └── scheduler.py         # Periodic execution manager
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared mock fixtures & sample payloads
│   ├── unit/
│   │   ├── test_collectors.py   # HTTP, timeouts, retries, 403, 500
│   │   ├── test_parsers.py      # Schema transformations & empty data
│   │   ├── test_validators.py   # Missing columns, numeric checks, dups
│   │   ├── test_processors.py   # Normalizer, deduplicator, quality
│   │   ├── test_csv_exporter.py # Atomic write & safe idempotency
│   │   └── test_repository.py   # DB failure & graceful fallback
│   └── integration/
│       ├── test_pipeline.py     # End-to-end runs & failure isolation
│       └── test_api.py          # All 8 REST endpoints
├── data/
│   ├── raw/                     # Snapshots of raw responses
│   ├── processed/               # Standardized output CSV files
│   └── reports/                 # JSON execution audit reports
├── logs/                        # Rotating structured log files
├── scripts/
│   ├── init_db.py               # Database migration & schema setup
│   └── generate_sample_outputs.py # Deliverable CSV & report generator
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI workflow
├── Dockerfile                   # Multi-stage production container
├── docker-compose.yml           # App + PostgreSQL orchestration
├── requirements.txt             # Locked production dependencies
├── .env.example                 # Environment configuration template
├── .gitignore                   # Version control exclusion rules
├── LICENSE                      # MIT Open Source License
├── main.py                      # Primary CLI entrypoint
└── README.md                    # Comprehensive platform documentation
```

---

## 7. Installation Instructions

### Prerequisites
- Python 3.11 or higher
- Git (optional, for cloning)
- PostgreSQL 14+ (optional, only if enabling database persistence)

### Step 1: Clone or Navigate to the Repository
```bash
cd E:\NSE
```

### Step 2: Create and Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 8. Environment Configuration

All configuration is managed via environment variables with production defaults. To customize, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default Value | Description |
|---|---|---|
| `NSE_BASE_URL` | `https://www.nseindia.com` | Base URL for official NSE India website |
| `NSE_REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `NSE_RETRY_COUNT` | `3` | Maximum retry attempts for transient HTTP errors |
| `NSE_RETRY_BACKOFF_FACTOR`| `2.0` | Exponential backoff multiplier |
| `NSE_RATE_LIMIT_DELAY` | `1.5` | Minimum delay (seconds) between requests |
| `OUTPUT_DIR` | `data/processed` | Destination directory for final CSV files |
| `RAW_OUTPUT_DIR` | `data/raw` | Raw response debug snapshots |
| `REPORTS_DIR` | `data/reports` | JSON execution audit reports directory |
| `LOG_DIR` | `logs` | Structured log output directory |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DB_ENABLED` | `false` | Enable PostgreSQL storage |
| `DATABASE_URL` | `postgresql://nse_user:nse_password@localhost:5432/nse_pulse` | PostgreSQL connection string |
| `SCHEDULER_ENABLED` | `false` | Enable automated periodic runs |
| `SCHEDULER_INTERVAL_MINUTES`| `60` | Scheduled interval between runs |

---

## 9. Execution Commands

### 1. Execute All Datasets (Default Mode)
Retrieves, validates, and exports all four datasets:
```bash
python main.py
# or explicitly:
python main.py --all
```

### 2. Execute Individual Datasets
```bash
# Top Gainers & Losers
python main.py --dataset top-gainers-losers

# Upper Band Hitters
python main.py --dataset upper-band-hitters

# Volume Gainers / Spurts
python main.py --dataset volume-gainers-spurts

# 52-Week High Equity
python main.py --dataset 52-week-high-equity
```

### 3. Specify Historical Trading Date
```bash
python main.py --all --date 2026-11-11
```

### 4. Start REST API & Visual Dashboard
```bash
python main.py --serve --port 8000
```
Open [http://localhost:8000](http://localhost:8000) for the Interactive Dashboard, or [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI.

### 5. Start Streamlit Analytics Dashboard
```bash
python main.py --dashboard
# or directly:
streamlit run dashboard.py
```
Open [http://localhost:8501](http://localhost:8501) for the full-featured analytics dashboard featuring interactive charts, volume spurt visualizers, quality breakdown, and on-demand ingestion controls.

### 6. Start Scheduled Automated Daemon
```bash
python main.py --schedule --interval 60
```

---

## 10. Data Acquisition Methodology

### Permitted Data Access & Ethics
NSE Pulse strictly conforms to ethical data acquisition standards:
- **No Anti-Bot Bypass**: Does not use CAPTCHA solvers, reverse-engineered tokens, or illicit proxy networks.
- **Session-Based Access**: Initializes a clean HTTP session by requesting `https://www.nseindia.com` to obtain standard session cookies before invoking live analysis endpoints.
- **Respectful Headers**: Sends standard browser user-agent and accept headers (`application/json, text/plain`).
- **Throttling & Backoff**: Automatically sleeps for `NSE_RATE_LIMIT_DELAY` seconds between requests and uses exponential backoff (`delay = backoff_factor ** attempt`) on transient timeouts.
- **Access Control Respect**: If an endpoint responds with HTTP 403 Forbidden, the client logs the restriction transparently and halts immediately without spamming retries.

---

## 11. Data Validation Methodology

The `ValidationEngine` evaluates every incoming record against an explicit schema contract. Invalid records are marked with `_is_valid=False` and logged with their field, row index, and root cause—**records are never silently dropped**.

### Validation Rule Matrix

| Rule | Severity | Condition | Action Taken |
|---|---|---|---|
| `required_columns` | ERROR | Expected column missing from API response | Marked invalid, reported in missing_columns |
| `empty_dataset` | WARNING | API response contains zero records | Flagged as warning, execution summary reflects 0 count |
| `missing_values` | ERROR | Critical field (e.g. `symbol`) is null or blank | Row flagged invalid, recorded in validation report |
| `numeric_validity` | ERROR | Price, quantity, or percentage cannot be parsed to float | Row flagged invalid, logged with problematic value |
| `duplicate_records`| WARNING | Duplicate `(symbol, category)` detected in batch | Logged in duplicate audit report |
| `data_type_check` | WARNING | Numeric column contains non-standard representation | Normalized or flagged for review |

---

## 12. CSV Storage Strategy

### Naming Conventions
Files are saved with ISO date stamps to guarantee chronological sorting:
- `top_gainers_losers_YYYY-MM-DD.csv`
- `upper_band_hitters_YYYY-MM-DD.csv`
- `volume_gainers_spurts_YYYY-MM-DD.csv`
- `52_week_high_equity_YYYY-MM-DD.csv`

### Atomic File Operations
To eliminate the risk of partial file writes or corruption during process termination:
1. The DataFrame is written to a temporary file (`.tmp`) within the destination directory.
2. The file is flushed and synced to disk via `os.fsync`.
3. `os.replace()` swaps the temporary file into the final destination atomically.

### Idempotent Re-execution
Running the pipeline multiple times on the same trading day safely replaces the file atomically without creating duplicate filenames (e.g., `(1).csv`), ensuring deterministic outcomes.

---

## 13. Duplicate Handling

1. **Hash-Based Detection**: The `DuplicateDetector` generates a deterministic SHA-256 hash across primary business key columns (`symbol`, `category`, `trade_date`).
2. **Audit Tracking**: All duplicate rows are logged with their index and payload before removal.
3. **Database Constraints**: The PostgreSQL schema enforces a unique constraint on `(dataset_name, symbol, trade_date)` using `ON CONFLICT DO UPDATE` (upsert) to guarantee database integrity across runs.

---

## 14. Error Handling & Failure Isolation

NSE Pulse implements fault isolation at the dataset level:
- Each dataset is processed in an independent `try/except` block inside `PipelineOrchestrator.process_dataset()`.
- If `upper-band-hitters` encounters a network glitch or restricted endpoint, the orchestrator logs the error, marks that dataset as `FAILED`, and continues to ingest `top-gainers-losers`, `volume-gainers-spurts`, and `52-week-high-equity`.
- The overall execution report reflects `PARTIAL_SUCCESS` with full visibility into which dataset encountered issues.

---

## 15. REST API Documentation

The platform provides a comprehensive FastAPI REST API.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System readiness, directory verification, database status |
| `GET` | `/datasets` | Metadata list of all 4 supported datasets |
| `GET` | `/datasets/{name}` | View latest downloaded records from CSV for a dataset |
| `POST` | `/download/{name}` | Trigger immediate on-demand download for an individual dataset |
| `POST` | `/download/all` | Trigger immediate pipeline run for all four datasets |
| `GET` | `/runs` | Historical execution runs with record counts and durations |
| `GET` | `/validation/{name}` | Latest validation report, issues, and duplicate stats |
| `GET` | `/metrics` | Operational health metrics, availability, average durations |
| `GET` | `/docs` | Interactive Swagger UI documentation |
| `GET` | `/dashboard` | Interactive Web Monitoring Dashboard |

---

## 16. Database Schema (PostgreSQL)

When `DB_ENABLED=true`, data is persisted to PostgreSQL:

```mermaid
erDiagram
    pipeline_runs {
        string id PK "UUID"
        timestamp started_at
        timestamp completed_at
        string status "SUCCESS / PARTIAL / FAILED"
        int datasets_attempted
        int datasets_succeeded
        int datasets_failed
        json summary
    }

    dataset_results {
        string id PK "UUID"
        string run_id FK
        string dataset_name
        string status
        int records_fetched
        int records_valid
        int records_rejected
        int duplicates_found
        float quality_score
        float processing_seconds
        string csv_file_path
        json validation_report
        timestamp created_at
    }

    stock_records {
        string id PK "UUID"
        string dataset_result_id FK
        string dataset_name "Indexed"
        string symbol "Indexed"
        string series
        date trade_date "Indexed"
        float ltp
        float pct_change
        float traded_qty
        json raw_data
        timestamp created_at
    }

    pipeline_runs ||--o{ dataset_results : "contains"
    dataset_results ||--o{ stock_records : "persists"
```

---

## 17. Automation

### 1. Cron / Scheduled Daemon
Run NSE Pulse continuously with an automated execution interval:
```bash
python main.py --schedule --interval 60
```

### 2. Docker Execution
Deploy the full platform with PostgreSQL using Docker Compose:
```bash
docker-compose up -d
```

---

## 18. Testing Instructions

NSE Pulse includes a comprehensive suite of 29 tests covering all 15 test scenarios specified in the assignment.

### Run Full Test Suite
```bash
pytest tests/ -v
```

### Run with Coverage Report
```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

### Test Scenarios Coverage Summary
1. **Successful download**: `tests/unit/test_collectors.py::test_successful_download`
2. **Connection timeout**: `tests/unit/test_collectors.py::test_connection_timeout_and_retries`
3. **HTTP 403 & 500 handling**: `tests/unit/test_collectors.py::test_http_403...` and `...test_http_500...`
4. **Invalid response format**: `tests/unit/test_collectors.py::test_invalid_json_response`
5. **Empty dataset**: `tests/unit/test_validators.py::test_empty_dataset_validation`
6. **Missing expected columns**: `tests/unit/test_validators.py::test_missing_expected_columns`
7. **Duplicate records**: `tests/unit/test_validators.py::test_duplicate_records_detection`
8. **Invalid numeric values**: `tests/unit/test_validators.py::test_invalid_numeric_values`
9. **CSV file creation**: `tests/unit/test_csv_exporter.py::test_csv_file_creation`
10. **Repeated execution**: `tests/unit/test_csv_exporter.py::test_repeated_execution_is_safe_and_idempotent`
11. **Individual dataset download**: `tests/integration/test_pipeline.py::test_individual_dataset_download`
12. **All four datasets downloading**: `tests/integration/test_pipeline.py::test_all_four_datasets_download_and_produce_csvs`
13. **Database failure**: `tests/unit/test_repository.py::test_database_failure_operates_gracefully`
14. **Retry behavior**: `tests/unit/test_collectors.py::test_connection_timeout_and_retries`
15. **API endpoint responses**: `tests/integration/test_api.py` (all 8 endpoints)

---

## 19. Sample Execution Output

### CLI Execution Summary
```
======================================================================
                NSE PULSE EXECUTION SUMMARY
======================================================================
Run ID:            67902434
Overall Status:    SUCCESS
Datasets Ran:      4/4 succeeded
Total Duration:    1.24 seconds
----------------------------------------------------------------------
Dataset                      | Status   | Valid  | Rejected | Quality
----------------------------------------------------------------------
top-gainers-losers           | SUCCESS  | 9      | 0        | 100.0 (A)
  └─ CSV: data\processed\top_gainers_losers_2026-11-11.csv
upper-band-hitters           | SUCCESS  | 4      | 0        | 100.0 (A)
  └─ CSV: data\processed\upper_band_hitters_2026-11-11.csv
volume-gainers-spurts        | SUCCESS  | 5      | 0        | 94.5 (A)
  └─ CSV: data\processed\volume_gainers_spurts_2026-11-11.csv
52-week-high-equity          | SUCCESS  | 4      | 0        | 100.0 (A)
  └─ CSV: data\processed\52_week_high_equity_2026-11-11.csv
======================================================================
```

### Sample CSV Output (`top_gainers_losers_2026-11-11.csv`)
```csv
symbol,series,open_price,high_price,low_price,ltp,prev_close,change,pct_change,traded_qty,trade_date,category
TCS,EQ,3450.0,3520.0,3440.0,3510.0,3430.0,80.0,2.33,1420500.0,2026-11-11,gainer
INFY,EQ,1520.0,1565.0,1515.0,1558.0,1510.0,48.0,3.18,3210400.0,2026-11-11,gainer
WIPRO,EQ,480.0,495.0,478.0,492.5,475.0,17.5,3.68,2540100.0,2026-11-11,gainer
HCLTECH,EQ,1340.0,1380.0,1335.0,1375.0,1330.0,45.0,3.38,1890200.0,2026-11-11,gainer
TECHM,EQ,1190.0,1225.0,1185.0,1218.0,1180.0,38.0,3.22,1105300.0,2026-11-11,gainer
RELIANCE,EQ,2460.0,2470.0,2390.0,2405.0,2455.0,-50.0,-2.04,4210000.0,2026-11-11,loser
ONGC,EQ,210.0,212.0,204.0,205.5,209.5,-4.0,-1.91,7850000.0,2026-11-11,loser
BPCL,EQ,380.0,382.0,371.0,373.0,379.0,-6.0,-1.58,3120000.0,2026-11-11,loser
IOC,EQ,142.0,143.0,138.5,139.2,141.5,-2.3,-1.63,6540000.0,2026-11-11,loser
```

---

## 20. Limitations and Assumptions

1. **Exchange Operating Hours**: NSE India market data is refreshed dynamically during active market hours (09:15 AM to 03:30 PM IST on trading days). Queries executed on weekends or market holidays return the closing values of the last trading session.
2. **Public Endpoint Constraints**: Public endpoints on `nseindia.com` occasionally update internal routing keys or require refreshed browser session tokens. NSE Pulse gracefully catches and logs these without terminating the process.
3. **Data Quality Score Scope**: The 4-dimension Data Quality Score (Completeness, Conformity, Duplicates, Types) is an internal engineering assessment tool and not an official NSE compliance rating.
4. **Historical Change Baseline**: On the very first run of the application, change detection establishes a baseline; subsequent runs automatically detect additions, drops, and shifts.

---

## 21. Future Improvements

- **Websocket / Tick Ingestion**: Add streaming support for real-time order-book updates via authorized broker APIs (e.g. Zerodha Kite, Upstox).
- **Parquet & DuckDB Storage**: Implement columnar Parquet exports with Snappy compression for analytical workloads.
- **Alert Webhooks**: Add Slack and Discord webhook integrations for instant alerting on validation anomalies or pipeline failures.
- **Kubernetes Helm Chart**: Package deployment manifests for scalable distributed deployment in cloud environments.

---

## 22. Verification Checklist

| Criterion | Status | Verification Reference |
|---|---|---|
| All 4 datasets retrieved automatically | ✅ Complete | `app/collectors/*.py` |
| 4 separate CSV files produced with date stamps | ✅ Complete | `data/processed/*.csv` |
| Individual dataset download supported | ✅ Complete | `python main.py --dataset <name>` |
| Failure isolation between datasets | ✅ Complete | `tests/integration/test_pipeline.py::test_dataset_failure_isolation` |
| Reusable validation engine with report | ✅ Complete | `app/validators/engine.py` |
| Duplicate detection and safe idempotency | ✅ Complete | `app/processors/deduplicator.py` |
| Structured JSON logging with required fields | ✅ Complete | `app/monitoring/logging_config.py` |
| Optional PostgreSQL with SQLAlchemy | ✅ Complete | `app/storage/repository.py` |
| FastAPI REST service with all 8 endpoints | ✅ Complete | `tests/integration/test_api.py` |
| Interactive Web Monitoring Dashboard | ✅ Complete | `GET /` and `GET /dashboard` |
| Comprehensive Pytest suite (29/29 passed) | ✅ Complete | `pytest tests/ -v` (78% coverage) |
| Docker & Docker Compose setup | ✅ Complete | `Dockerfile`, `docker-compose.yml` |
| GitHub Actions CI/CD Pipeline | ✅ Complete | `.github/workflows/ci.yml` |

