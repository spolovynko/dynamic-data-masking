from __future__ import annotations

import logging

from apps.worker.celery_app import celery_app
from ddm_engine.config import Settings
from ddm_engine.storage.jobs import JobNotFoundError
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository

logger = logging.getLogger(__name__)


@celery_app.task(name="ddm.process_document")
def process_document(job_id: str) -> dict[str, str]:
    settings = Settings()
    repository = SqlAlchemyDocumentJobRepository.from_settings(settings)

    try:
        job = repository.get(job_id)
    except JobNotFoundError:
        logger.warning("Worker received unknown job", extra={"job_id": job_id})
        raise

    logger.info(
        "Worker accepted document processing job",
        extra={"job_id": job_id, "status": job.status.value},
    )
    return {
        "job_id": job_id,
        "status": job.status.value,
        "message": "Worker skeleton accepted the job; extraction is the next implementation step.",
    }
