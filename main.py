"""NSE Pulse – Intelligent Market Data Engineering Platform.

CLI Entrypoint supporting:
- python main.py                             (downloads all 4 datasets)
- python main.py --all                       (explicit download all)
- python main.py --dataset <dataset_name>    (download single dataset)
- python main.py --serve                     (launch FastAPI REST API & Dashboard)
- python main.py --schedule                  (run periodic automated pipeline)
"""

import argparse
import sys
import time
from datetime import datetime
from typing import List, Optional

from app.config.settings import DatasetConfig, get_settings
from app.monitoring.logging_config import setup_logging
from app.scheduler.scheduler import PipelineScheduler
from app.services.orchestrator import PipelineOrchestrator


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="nse-pulse",
        description="NSE Pulse – Intelligent Market Data Engineering Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --all
  python main.py --dataset top-gainers-losers
  python main.py --dataset upper-band-hitters
  python main.py --dataset volume-gainers-spurts
  python main.py --dataset 52-week-high-equity
  python main.py --serve --port 8000
  python main.py --schedule --interval 60
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dataset",
        type=str,
        choices=DatasetConfig.get_dataset_names(),
        help="Specify an individual dataset to retrieve and process.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Retrieve all four registered datasets (default if no flags passed).",
    )
    group.add_argument(
        "--serve",
        action="store_true",
        help="Start the FastAPI REST server and web dashboard.",
    )
    group.add_argument(
        "--dashboard",
        action="store_true",
        help="Start the interactive Streamlit analytics dashboard.",
    )
    group.add_argument(
        "--schedule",
        action="store_true",
        help="Run as a background daemon executing on a periodic schedule.",
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Explicit trade date in YYYY-MM-DD format (defaults to current system date).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the REST API server (used with --serve). Default: 8000.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for the REST API server (used with --serve). Default: 0.0.0.0.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Interval in minutes for scheduled runs (used with --schedule).",
    )

    return parser.parse_args()


def run_cli_pipeline(
    dataset: Optional[str] = None,
    trade_date_str: Optional[str] = None,
) -> int:
    """Execute the pipeline via CLI and return an exit code."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_dir=settings.log_dir)

    trade_date = None
    if trade_date_str:
        try:
            trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{trade_date_str}'. Expected YYYY-MM-DD.")
            return 1

    orchestrator = PipelineOrchestrator(settings)

    if dataset:
        target_datasets = [dataset]
    else:
        target_datasets = DatasetConfig.get_dataset_names()

    report = orchestrator.run(
        dataset_names=target_datasets,
        execution_date=trade_date,
    )

    # CLI Output Display
    print("\n" + "=" * 70)
    print("                NSE PULSE EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Run ID:            {report.run_id}")
    print(f"Overall Status:    {report.overall_status}")
    print(f"Datasets Ran:      {report.datasets_succeeded}/{report.datasets_attempted} succeeded")
    print(f"Total Duration:    {report.total_duration_seconds:.2f} seconds")
    print("-" * 70)
    print(f"{'Dataset':<28} | {'Status':<8} | {'Valid':<6} | {'Rejected':<8} | {'Quality'}")
    print("-" * 70)

    for name, sumry in report.datasets.items():
        q_score_str = f"{sumry.quality_score:.1f} ({sumry.quality_grade})" if sumry.quality_score else "N/A"
        print(
            f"{name:<28} | {sumry.status:<8} | {sumry.records_valid:<6} | {sumry.records_rejected:<8} | {q_score_str}"
        )
        if sumry.csv_file_path:
            print(f"  └─ CSV: {sumry.csv_file_path}")
        if sumry.error_message:
            print(f"  └─ Error: {sumry.error_message}")

    print("=" * 70 + "\n")

    return 0 if report.overall_status in ("SUCCESS", "PARTIAL_SUCCESS") else 1


def start_server(host: str, port: int) -> None:
    """Start Uvicorn server hosting FastAPI."""
    import uvicorn
    from app.api.app import create_app

    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_dir=settings.log_dir)

    print(f"Starting NSE Pulse API & Dashboard on http://{host}:{port} ...")
    uvicorn.run("app.api.app:create_app", host=host, port=port, factory=True, reload=False)


def start_scheduler(interval_minutes: Optional[int]) -> None:
    """Start periodic scheduled pipeline execution."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_dir=settings.log_dir)

    interval = interval_minutes or settings.scheduler_interval_minutes
    orchestrator = PipelineOrchestrator(settings)

    print(f"Starting NSE Pulse Scheduler (every {interval} minutes). Press Ctrl+C to stop.")

    def _scheduled_task():
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running scheduled pipeline...")
        orchestrator.run()

    scheduler = PipelineScheduler(interval_minutes=interval, task=_scheduled_task)
    scheduler.start()

    # Trigger one immediate execution
    _scheduled_task()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        scheduler.stop()


def start_dashboard(port: int = 8501) -> None:
    """Start Streamlit analytics dashboard."""
    import subprocess

    print(f"Starting NSE Pulse Streamlit Dashboard on http://localhost:{port} ...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py", "--server.port", str(port)])


def main() -> None:
    """Main CLI entrypoint."""
    args = parse_arguments()

    if args.serve:
        start_server(host=args.host, port=args.port)
        sys.exit(0)
    elif args.dashboard:
        start_dashboard(port=8501)
        sys.exit(0)
    elif args.schedule:
        start_scheduler(interval_minutes=args.interval)
        sys.exit(0)
    elif args.dataset:
        exit_code = run_cli_pipeline(dataset=args.dataset, trade_date_str=args.date)
        sys.exit(exit_code)
    else:
        # Default behavior or --all: run all datasets
        exit_code = run_cli_pipeline(dataset=None, trade_date_str=args.date)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()

