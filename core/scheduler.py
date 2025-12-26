"""
Sync scheduler for daily automated syncs.

Uses APScheduler for reliable scheduling with timezone support.
"""

import logging
from datetime import datetime
from typing import Callable, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
import pytz

from .config import SyncConfig

logger = logging.getLogger(__name__)


class SyncScheduler:
    """
    Scheduler for automated daily syncs.

    Supports:
    - Daily scheduled sync at configured time (default 2am)
    - Manual trigger for on-demand sync
    - Job tracking and error logging
    """

    def __init__(self, config: SyncConfig):
        self.config = config
        self.scheduler = BackgroundScheduler(
            timezone=pytz.timezone(config.timezone)
        )
        self._sync_jobs: dict[str, str] = {}  # name -> job_id mapping
        self._last_run: dict[str, datetime] = {}
        self._last_error: dict[str, str] = {}

        # Add event listeners
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)

    def _on_job_executed(self, event: JobExecutionEvent):
        """Handle successful job execution."""
        job_id = event.job_id
        self._last_run[job_id] = datetime.now(pytz.timezone(self.config.timezone))
        self._last_error.pop(job_id, None)
        logger.info(f"Sync job {job_id} completed successfully")

    def _on_job_error(self, event: JobExecutionEvent):
        """Handle job execution error."""
        job_id = event.job_id
        self._last_run[job_id] = datetime.now(pytz.timezone(self.config.timezone))
        self._last_error[job_id] = str(event.exception)
        logger.error(f"Sync job {job_id} failed: {event.exception}")

    def add_daily_sync(
        self,
        name: str,
        sync_func: Callable,
        hour: int = None,
        minute: int = None,
    ) -> str:
        """
        Add a daily sync job.

        Args:
            name: Unique name for this sync job
            sync_func: Function to call for sync (should accept no args)
            hour: Hour to run (default: config.schedule_hour)
            minute: Minute to run (default: config.schedule_minute)

        Returns:
            Job ID
        """
        hour = hour if hour is not None else self.config.schedule_hour
        minute = minute if minute is not None else self.config.schedule_minute

        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=pytz.timezone(self.config.timezone),
        )

        job = self.scheduler.add_job(
            sync_func,
            trigger=trigger,
            id=f"sync_{name}",
            name=f"Daily sync: {name}",
            replace_existing=True,
        )

        self._sync_jobs[name] = job.id
        logger.info(f"Added daily sync job '{name}' at {hour:02d}:{minute:02d} {self.config.timezone}")

        return job.id

    def trigger_now(self, name: str = None) -> List[str]:
        """
        Trigger sync immediately.

        Args:
            name: Specific job to trigger, or None for all jobs

        Returns:
            List of triggered job IDs
        """
        triggered = []

        if name:
            job_id = self._sync_jobs.get(name)
            if job_id:
                job = self.scheduler.get_job(job_id)
                if job:
                    job.modify(next_run_time=datetime.now(pytz.timezone(self.config.timezone)))
                    triggered.append(job_id)
                    logger.info(f"Triggered immediate sync for '{name}'")
        else:
            # Trigger all jobs
            for job_name, job_id in self._sync_jobs.items():
                job = self.scheduler.get_job(job_id)
                if job:
                    job.modify(next_run_time=datetime.now(pytz.timezone(self.config.timezone)))
                    triggered.append(job_id)
                    logger.info(f"Triggered immediate sync for '{job_name}'")

        return triggered

    def get_status(self) -> dict:
        """Get status of all sync jobs."""
        status = {}
        tz = pytz.timezone(self.config.timezone)

        for name, job_id in self._sync_jobs.items():
            job = self.scheduler.get_job(job_id)
            if job:
                status[name] = {
                    "job_id": job_id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "last_run": self._last_run.get(job_id, {}).isoformat() if self._last_run.get(job_id) else None,
                    "last_error": self._last_error.get(job_id),
                    "is_paused": job.next_run_time is None,
                }

        return status

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Sync scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Sync scheduler stopped")

    def pause_job(self, name: str):
        """Pause a specific sync job."""
        job_id = self._sync_jobs.get(name)
        if job_id:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused sync job '{name}'")

    def resume_job(self, name: str):
        """Resume a paused sync job."""
        job_id = self._sync_jobs.get(name)
        if job_id:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed sync job '{name}'")


class SyncRunner:
    """
    Convenience class to run syncs with logging and error handling.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"sync.{name}")

    def run(self, sync_func: Callable, *args, **kwargs) -> dict:
        """
        Run a sync function with timing and error handling.

        Returns dict with status, duration, and any errors.
        """
        start_time = datetime.utcnow()
        self.logger.info(f"Starting {self.name} sync")

        try:
            result = sync_func(*args, **kwargs)
            duration = (datetime.utcnow() - start_time).total_seconds()

            self.logger.info(f"Completed {self.name} sync in {duration:.2f}s")

            return {
                "status": "success",
                "name": self.name,
                "duration_seconds": duration,
                "started_at": start_time.isoformat(),
                "result": result,
            }

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(f"Failed {self.name} sync after {duration:.2f}s: {e}")

            return {
                "status": "error",
                "name": self.name,
                "duration_seconds": duration,
                "started_at": start_time.isoformat(),
                "error": str(e),
            }
