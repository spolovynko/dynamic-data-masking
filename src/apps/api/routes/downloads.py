from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from apps.api.auth import RequestActor, assert_job_access, get_request_actor
from ddm_engine.config import Settings
from ddm_engine.storage.jobs import JobNotFoundError, JobStatus, JobStore
from ddm_engine.storage.object_store import create_object_store

router = APIRouter(tags=["downloads"])


@router.get("/jobs/{job_id}/download")
def download_redacted_document(
    job_id: str,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> Response:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    if job.status != JobStatus.READY or job.redacted_object_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redacted document is not available for this job yet",
        )

    object_store = create_object_store(Settings())
    if not object_store.exists(job.redacted_object_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redacted document artifact is missing",
        )

    filename = f"{job.job_id}-redacted.pdf"
    return Response(
        content=object_store.read_bytes(job.redacted_object_key),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
