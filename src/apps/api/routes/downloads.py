from fastapi import APIRouter, HTTPException, Response, status

from apps.api.dependencies import AuthorizedJobDep, ObjectStoreDep, require_artifact
from ddm_engine.storage.jobs import JobStatus

router = APIRouter(tags=["downloads"])


@router.get("/jobs/{job_id}/download")
def download_redacted_document(
    job: AuthorizedJobDep,
    object_store: ObjectStoreDep,
) -> Response:
    if job.status != JobStatus.READY or job.redacted_object_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redacted document is not available for this job yet",
        )

    require_artifact(object_store, job.redacted_object_key, "Redacted document artifact is missing")

    filename = f"{job.job_id}-redacted.pdf"
    return Response(
        content=object_store.read_bytes(job.redacted_object_key),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
