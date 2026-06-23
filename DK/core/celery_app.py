from celery import Celery
from celery.schedules import crontab
import os

def create_celery_app() -> Celery:
    app = Celery(
        "parking_system",
        broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
        include=[
            "tasks.parking_tasks",
            "tasks.report_tasks",
            "tasks.notification_tasks",
            "tasks.recognition_tasks"
        ]
    )

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Europe/Moscow",
        enable_utc=True,
        worker_max_tasks_per_child=1000,
        task_track_started=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        beat_schedule={
            "check-expiring-sessions-every-minute": {
                "task": "tasks.parking_tasks.check_expiring_sessions",
                "schedule": 60.0,
                "args": ()
            },
            "generate-daily-financial-report": {
                "task": "tasks.report_tasks.generate_daily_report",
                "schedule": crontab(hour=2, minute=0),
                "args": ()
            },
            "sync-parking-spot-sensors": {
                "task": "tasks.parking_tasks.sync_sensor_data",
                "schedule": crontab(minute="*/5"),
                "args": ()
            },
            "cleanup-stale-sessions": {
                "task": "tasks.parking_tasks.cleanup_stale_sessions",
                "schedule": crontab(minute=0, hour="*"),
                "args": ()
            },
        },
        task_routes={
            "tasks.report_tasks.*": {"queue": "reports"},
            "tasks.notification_tasks.*": {"queue": "notifications"},
            "tasks.parking_tasks.*": {"queue": "default"},
            "tasks.recognition_tasks.*": {"queue": "recognition"},
        },
        worker_concurrency=4,
    )

    return app

celery_app = create_celery_app()