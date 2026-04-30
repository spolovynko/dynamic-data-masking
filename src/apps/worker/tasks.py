from __future__ import annotations

import logging
import time
from dataclasses import dataclass

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


@dataclass(frozen=True)
class ProcessingServices:
    repository: SqlAlchemyDocumentJobRepository
    extraction: ExtractionService
    detection: DetectionService
    planning: RedactionPlanningService
    redaction: PDFRedactionService
    quality: RedactionQualityService


@celery_app.task(name="ddm.process_document")
def process_document(job_id: str, correlation_id: str | None = None) -> dict[str, str]:
    started_at = time.perf_counter()
    context_tokens = set_observability_context(correlation_id or job_id, correlation_id or job_id)
    services = _build_processing_services(Settings())

    try:
        return _process_job(job_id, started_at, services)
    finally:
        reset_observability_context(context_tokens)


def _build_processing_services(settings: Settings) -> ProcessingServices:
    object_store = create_object_store(settings)
    return ProcessingServices(
        repository=SqlAlchemyDocumentJobRepository.from_settings(settings),
        extraction=ExtractionService(object_store),
        detection=DetectionService(object_store),
        planning=RedactionPlanningService(object_store),
        redaction=PDFRedactionService(object_store),
        quality=RedactionQualityService(object_store),
    )


def _process_job(
    job_id: str,
    started_at: float,
    services: ProcessingServices,
) -> dict[str, str]:
    try:
        job = services.repository.get(job_id)
    except JobNotFoundError:
        logger.warning("Worker received unknown job", extra={"job_id": job_id})
        raise

    if job.status == JobStatus.READY and job.redacted_object_key:
        return {
            "job_id": job_id,
            "status": JobStatus.READY.value,
            "message": "Job is already ready",
            "redacted_object_key": job.redacted_object_key,
        }

    try:
        services.repository.update_status(job_id, JobStatus.EXTRACTING)
        logger.info("Document processing started", extra={"job_id": job_id})

        result = services.extraction.extract_layout(job)
        services.repository.update_status(job_id, JobStatus.DETECTING)
        detection_result = services.detection.detect(job)
        services.repository.update_status(job_id, JobStatus.PLANNING_REDACTIONS)
        redaction_plan = services.planning.plan(job)
        services.repository.update_status(job_id, JobStatus.REDACTING)
        redacted_object_key = services.redaction.redact(job)
        services.repository.update_status(job_id, JobStatus.VERIFYING)
        verification_report = services.quality.verify(job, redacted_object_key)

        if not services.quality.passed(verification_report):
            return _fail_verification(job_id, started_at, services, verification_report.leak_count)

        services.repository.update_redacted_output(job_id, redacted_object_key, JobStatus.READY)
    except ExtractionError:
        _record_failure(
            services,
            job_id,
            JobStatus.FAILED,
            "extraction_failed",
            started_at,
            "Document extraction failed",
        )
        logger.exception("Document processing failed", extra={"job_id": job_id})
        raise
    except RedactionVerificationError:
        _record_failure(
            services,
            job_id,
            JobStatus.FAILED_VERIFICATION,
            "verification_error",
            started_at,
            "Redaction verification failed",
        )
        logger.exception("Redaction verification failed", extra={"job_id": job_id})
        raise
    except Exception:
        _record_failure(
            services,
            job_id,
            JobStatus.FAILED,
            "processing_failed",
            started_at,
            "Document processing failed",
        )
        logger.exception("Document processing failed", extra={"job_id": job_id})
        raise

    _record_duration(JobStatus.READY, started_at)
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
    return {
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


def _fail_verification(
    job_id: str,
    started_at: float,
    services: ProcessingServices,
    leak_count: int,
) -> dict[str, str]:
    _record_failure(
        services,
        job_id,
        JobStatus.FAILED_VERIFICATION,
        "verification_failed",
        started_at,
        "Sensitive text leakage detected after redaction",
    )
    return {
        "job_id": job_id,
        "status": JobStatus.FAILED_VERIFICATION.value,
        "leak_count": str(leak_count),
    }


def _record_failure(
    services: ProcessingServices,
    job_id: str,
    status: JobStatus,
    metric_reason: str,
    started_at: float,
    failure_reason: str,
) -> None:
    services.repository.update_status(job_id, status, failure_reason=failure_reason)
    JOB_FAILURES_TOTAL.labels(reason=metric_reason).inc()
    _record_duration(status, started_at)


def _record_duration(final_status: JobStatus, started_at: float) -> None:
    JOB_DURATION_SECONDS.labels(final_status=final_status.value).observe(
        time.perf_counter() - started_at
    )
