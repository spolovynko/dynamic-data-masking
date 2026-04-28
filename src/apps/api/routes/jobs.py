from fastapi import APIRouter, HTTPException, status

from apps.api import queue as api_queue
from apps.api.schemas.jobs import JobEnqueueResponse, JobResponse
from ddm_engine.storage.jobs import JobNotFoundError, JobStatus, JobStore

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return JobResponse(**job.to_response_dict())


@router.post("/jobs/{job_id}/process", response_model=JobEnqueueResponse)
def process_job(job_id: str) -> JobEnqueueResponse:
    store = JobStore.from_environment()
    try:
        queued_job = store.update_status(job_id, JobStatus.QUEUED)
        task = api_queue.enqueue_document_processing_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        store.update_status(
            job_id,
            JobStatus.UPLOADED,
            failure_reason="Failed to enqueue background job",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue background job",
        ) from exc

    return JobEnqueueResponse(**queued_job.to_response_dict(), task_id=task.task_id)
