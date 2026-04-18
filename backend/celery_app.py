from celery import Celery
from celery.schedules import crontab

from backend.config import settings

app = Celery(
    "sniper",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["backend.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="US/Central",
    enable_utc=True,
    beat_schedule={
        "scan-marketplace": {
            "task": "backend.tasks.scan_all",
            "schedule": settings.scan_interval_minutes * 60,
        },
    },
)
