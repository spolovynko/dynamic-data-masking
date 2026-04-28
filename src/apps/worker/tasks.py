from __future__ import annotations

import logging

from apps.worker.celery_app import celery_app
from ddm_engine.config import Settings
from ddm_engine.extraction.pdf_text import ExtractionError
from ddm_engine.extraction.service import ExtractionService
from ddm_engine.storage.jobs import JobNotFoundError, JobStatus
from ddm_engine.storage.object_store import create_object_store
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository

logger = logging.getLogger(__name__)


@celery_app.task(name="ddm.process_document")
def process_document(job_id: str) -> dict[str, str]:
    settings = Settings()
    repository = SqlAlchemyDocumentJobRepository.from_settings(settings)
    object_store = create_object_store(settings)
    extraction_service = ExtractionService(object_store)

    try:
        job = repository.get(job_id)
    except JobNotFoundError:
        logger.warning("Worker received unknown job", extra={"job_id": job_id})
        raise

    try:
        repository.update_status(job_id, JobStatus.EXTRACTING)

        if job.file_type != "pdf":
            repository.update_status(
                job_id,
                JobStatus.FAILED,
                failure_reason="Only PDF extraction is implemented",
            )
            return {
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "message": "Only PDF extraction is implemented",
            }

        result = extraction_service.extract_pdf_layout(job)
        repository.update_status(job_id, JobStatus.DETECTING)
    except ExtractionError as exc:
        repository.update_status(
            job_id,
            JobStatus.FAILED,
            failure_reason="PDF extraction failed",
        )
        raise exc

    return {
        "job_id": job_id,
        "status": JobStatus.DETECTING.value,
        "layout_object_key": result.layout_object_key,
        "page_count": str(result.page_count),
        "token_count": str(result.token_count),
    }
