"""EnergyPlus Celery worker (spec Ch 9.4).

Production async path: one worker = one concurrent EnergyPlus run; scale by
adding worker instances. The beta runs the same pipeline.run_job inline via
FastAPI BackgroundTasks, so Celery/Redis are optional. When REDIS_URL is set and
celery is installed, point the API's dispatcher at run_project_analysis.delay().

Run: celery -A workers.eplus_worker worker --loglevel=info --concurrency=1
"""
from __future__ import annotations

import os

try:
    from celery import Celery
except ImportError:  # celery is an optional (worker-image) dependency
    Celery = None  # type: ignore

from app.pipeline import run_job

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if Celery is not None:
    app = Celery("energy_modeler", broker=REDIS_URL, backend=REDIS_URL)
    app.conf.update(task_time_limit=1800, task_max_retries=2)

    @app.task(bind=True, max_retries=2, time_limit=1800)
    def run_project_analysis(self, job_id: str):
        """Run baseline + N candidate scenarios for one project."""
        try:
            run_job(job_id)
        except Exception as exc:  # noqa: BLE001
            raise self.retry(exc=exc, countdown=60)
