from __future__ import annotations

import logging
import time

from apps.worker.celery_app import celery_app
from ddm_engine.config import Settings
from ddm_engine.detection.service import DetectionService
from ddm_engine.extraction.pdf_text import ExtractionError
from ddm_engine.extraction.service import ExtractionService
from ddm_engine.observability.context import reset_observability_context, set_observability_context
from ddm_engine.observability.metrics import JOB_DURATION_SECONDS, JOB_FAILURES_TOTAL
from ddm_engine.planning.service import RedactionPlanningService
from ddm_engine.quality.service import RedactionQualityService
from ddm_engine.quality.verifier import RedactionVerificationError
from ddm_engine.rendering.pdf_redactor import PDFRedactionService
from ddm_engine.storage.jobs import JobNotFoundError, JobStatus
from ddm_engine.storage.object_store import create_object_store
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository

logger = logging.getLogger(__name__)


@celery_app.task(name="ddm.process_document")
def process_document(job_id: str, correlation_id: str | None = None) -> dict[str, str]:
    started_at = time.perf_counter()
    context_tokens = set_observability_context(correlation_id or job_id, correlation_id or job_id)
    settings = Settings()
    repository = SqlAlchemyDocumentJobRepository.from_settings(settings)
    object_store = create_object_store(settings)
    extraction_service = ExtractionService(object_store)
    detection_service = DetectionService(object_store)
    planning_service = RedactionPlanningService(object_store)
    redaction_service = PDFRedactionService(object_store)
    quality_service = RedactionQualityService(object_store)

    try:
        job = repository.get(job_id)
    except JobNotFoundError:
        logger.warning("Worker received unknown job", extra={"job_id": job_id})
        reset_observability_context(context_tokens)
        raise

    try:
        if job.status == JobStatus.READY and job.redacted_object_key:
            response = {
                "job_id": job_id,
                "status": JobStatus.READY.value,
                "message": "Job is already ready",
                "redacted_object_key": job.redacted_object_key,
            }
            reset_observability_context(context_tokens)
            return response

        repository.update_status(job_id, JobStatus.EXTRACTING)
        logger.info("Document processing started", extra={"job_id": job_id})

        result = extraction_service.extract_layout(job)
        repository.update_status(job_id, JobStatus.DETECTING)
        detection_result = detection_service.detect(job)
        repository.update_status(job_id, JobStatus.PLANNING_REDACTIONS)
        redaction_plan = planning_service.plan(job)
        repository.update_status(job_id, JobStatus.REDACTING)
        redacted_object_key = redaction_service.redact(job)
        repository.update_status(job_id, JobStatus.VERIFYING)
        verification_report = quality_service.verify(job, redacted_object_key)

        if not quality_service.passed(verification_report):
            repository.update_status(
                job_id,
                JobStatus.FAILED_VERIFICATION,
                failure_reason="Sensitive text leakage detected after redaction",
            )
            JOB_FAILURES_TOTAL.labels(reason="verification_failed").inc()
            JOB_DURATION_SECONDS.labels(final_status=JobStatus.FAILED_VERIFICATION.value).observe(
                time.perf_counter() - started_at
            )
            response = {
                "job_id": job_id,
                "status": JobStatus.FAILED_VERIFICATION.value,
                "leak_count": str(verification_report.leak_count),
            }
            reset_observability_context(context_tokens)
            return response

        repository.update_redacted_output(job_id, redacted_object_key, JobStatus.READY)
    except ExtractionError:
        repository.update_status(
            job_id,
            JobStatus.FAILED,
            failure_reason="Document extraction failed",
        )
        JOB_FAILURES_TOTAL.labels(reason="extraction_failed").inc()
        JOB_DURATION_SECONDS.labels(final_status=JobStatus.FAILED.value).observe(
            time.perf_counter() - started_at
        )
        logger.exception("Document processing failed", extra={"job_id": job_id})
        reset_observability_context(context_tokens)
        raise
    except RedactionVerificationError:
        repository.update_status(
            job_id,
            JobStatus.FAILED_VERIFICATION,
            failure_reason="Redaction verification failed",
        )
        JOB_FAILURES_TOTAL.labels(reason="verification_error").inc()
        JOB_DURATION_SECONDS.labels(final_status=JobStatus.FAILED_VERIFICATION.value).observe(
            time.perf_counter() - started_at
        )
        logger.exception("Redaction verification failed", extra={"job_id": job_id})
        reset_observability_context(context_tokens)
        raise
    except Exception:
        repository.update_status(
            job_id,
            JobStatus.FAILED,
            failure_reason="Document processing failed",
        )
        JOB_FAILURES_TOTAL.labels(reason="processing_failed").inc()
        JOB_DURATION_SECONDS.labels(final_status=JobStatus.FAILED.value).observe(
            time.perf_counter() - started_at
        )
        logger.exception("Document processing failed", extra={"job_id": job_id})
        reset_observability_context(context_tokens)
        raise

    JOB_DURATION_SECONDS.labels(final_status=JobStatus.READY.value).observe(
        time.perf_counter() - started_at
    )
    logger.info(
        "Document processing completed",
        extra={
            "job_id": job_id,
            "candidate_count": detection_result.candidate_count,
            "decision_count": redaction_plan.decision_count,
            "region_count": redaction_plan.region_count,
            "verification_status": verification_report.status.value,
        },
    )
    response = {
        "job_id": job_id,
        "status": JobStatus.READY.value,
        "layout_object_key": result.layout_object_key,
        "page_count": str(result.page_count),
        "token_count": str(result.token_count),
        "candidate_count": str(detection_result.candidate_count),
        "decision_count": str(redaction_plan.decision_count),
        "region_count": str(redaction_plan.region_count),
        "redacted_object_key": redacted_object_key,
        "verification_status": verification_report.status.value,
    }
    reset_observability_context(context_tokens)
    return response
