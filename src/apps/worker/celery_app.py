from celery import Celery

from ddm_engine.config import get_settings
from ddm_engine.observability.logging import configure_logging


def create_celery_app() -> Celery:
    settings = get_settings()
    configure_logging(settings.worker_log_level)
    celery_app = Celery(
        "dynamic_data_masking",
        broker=settings.queue_broker_url,
        backend=settings.queue_result_backend,
        include=["apps.worker.tasks"],
    )
    celery_app.conf.update(
        task_default_queue=settings.queue_name,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        enable_utc=True,
        timezone="UTC",
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=True,
        worker_hijack_root_logger=False,
        worker_redirect_stdouts=False,
    )
    return celery_app


celery_app = create_celery_app()
