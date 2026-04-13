from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "torque_backend",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
    beat_schedule={
        "sample-daily-heartbeat": {
            "task": "app.tasks.analysis_tasks.emit_heartbeat",
            "schedule": 3600.0,
        }
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
