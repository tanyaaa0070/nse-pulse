"""Pipeline Scheduler for automated periodic execution.

Supports recurring execution using APScheduler BackgroundScheduler,
or fallback threading Timer when APScheduler is unavailable.
"""

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("nse_pulse.scheduler")


class PipelineScheduler:
    """Manages periodic execution of pipeline tasks."""

    def __init__(self, interval_minutes: int, task: Callable[[], None]) -> None:
        self.interval_minutes = interval_minutes
        self.task = task
        self._scheduler = None
        self._thread = None
        self._running = False

    def start(self) -> None:
        """Start the background scheduler."""
        if self._running:
            logger.warning("Scheduler is already running.")
            return

        self._running = True
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler()
            self._scheduler.add_job(
                self.task,
                "interval",
                minutes=self.interval_minutes,
                id="nse_pulse_job",
                replace_existing=True,
            )
            self._scheduler.start()
            logger.info(
                "APScheduler started: running pipeline every %d minute(s).",
                self.interval_minutes,
            )
        except ImportError:
            logger.info(
                "APScheduler not found; starting lightweight background thread scheduler."
            )
            self._start_thread_scheduler()

    def _start_thread_scheduler(self) -> None:
        def _loop():
            while self._running:
                time.sleep(self.interval_minutes * 60)
                if self._running:
                    try:
                        logger.info("Executing scheduled pipeline run...")
                        self.task()
                    except Exception as exc:
                        logger.error("Error in scheduled run: %s", exc)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background scheduler."""
        self._running = False
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped.")
        if self._thread:
            logger.info("Background thread scheduler stopped.")

