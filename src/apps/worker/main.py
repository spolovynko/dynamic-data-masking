from apps.worker.celery_app import celery_app
from ddm_engine.config import get_settings


def run() -> None:
    settings = get_settings()
    celery_app.worker_main(
        [
            "worker",
            "--loglevel",
            settings.worker_log_level,
            "--queues",
            settings.queue_name,
            "--pool",
            settings.worker_pool,
        ]
    )
