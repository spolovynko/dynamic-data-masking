from prometheus_client import start_http_server

from apps.worker.celery_app import celery_app
from ddm_engine.config import get_settings
from ddm_engine.observability.logging import configure_logging


def run() -> None:
    settings = get_settings()
    configure_logging(settings.worker_log_level)
    start_http_server(settings.worker_metrics_port)
    celery_app.worker_main(
        [
            "--quiet",
            "worker",
            "--loglevel",
            settings.worker_log_level,
            "--queues",
            settings.queue_name,
            "--pool",
            settings.worker_pool,
        ]
    )
