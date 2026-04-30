from fastapi import APIRouter, HTTPException, status

from apps.api import queue as api_queue
from apps.api.dependencies import AuthorizedJobDep, JobStoreDep
from apps.api.schemas.jobs import JobEnqueueResponse, JobResponse
from ddm_engine.observability.context import get_observability_context
from ddm_engine.observability.metrics import JOBS_ENQUEUED_TOTAL
from ddm_engine.storage.jobs import JobStatus

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job: AuthorizedJobDep) -> JobResponse:
    return JobResponse(**job.to_response_dict())


@router.post("/jobs/{job_id}/process", response_model=JobEnqueueResponse)
def process_job(
    job_id: str,
    job: AuthorizedJobDep,
    store: JobStoreDep,
) -> JobEnqueueResponse:
    try:
        queued_job = store.update_status(job_id, JobStatus.QUEUED)
        task = api_queue.enqueue_document_processing_job(
            job_id,
            correlation_id=get_observability_context().correlation_id,
        )
    except Exception as exc:
        store.update_status(
            job.job_id,
            JobStatus.UPLOADED,
            failure_reason="Failed to enqueue background job",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue background job",
        ) from exc

    JOBS_ENQUEUED_TOTAL.inc()
    return JobEnqueueResponse(**queued_job.to_response_dict(), task_id=task.task_id)
