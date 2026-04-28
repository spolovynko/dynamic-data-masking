from dataclasses import dataclass

from apps.worker.celery_app import celery_app
from ddm_engine.config import Settings


@dataclass(frozen=True)
class EnqueuedTask:
    task_id: str


def enqueue_document_processing_job(job_id: str, correlation_id: str | None = None) -> EnqueuedTask:
    settings = Settings()
    result = celery_app.send_task(
        "ddm.process_document",
        args=[job_id, correlation_id],
        queue=settings.queue_name,
    )
    return EnqueuedTask(task_id=result.id)
