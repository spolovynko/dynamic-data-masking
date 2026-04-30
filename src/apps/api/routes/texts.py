import fitz
from fastapi import APIRouter, HTTPException, status

from apps.api.dependencies import AuthorizedJobDep, ObjectStoreDep, require_artifact
from apps.api.schemas.texts import DocumentTextResponse, TextPageResponse
from ddm_engine.detection.text_index import build_page_text_indexes
from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.jobs import JobStatus

router = APIRouter(tags=["document-text"])


@router.get("/jobs/{job_id}/text/extracted", response_model=DocumentTextResponse)
def get_extracted_text(
    job: AuthorizedJobDep,
    object_store: ObjectStoreDep,
) -> DocumentTextResponse:
    layout_key = ArtifactKeys.layout(job.job_id)
    require_artifact(object_store, layout_key, "Extracted text is not available for this job yet")

    layout = JsonArtifactStore(object_store).read_model(layout_key, DocumentLayout)
    pages = [
        TextPageResponse(page_number=index.page_number, text=index.text)
        for index in build_page_text_indexes(layout)
    ]
    return DocumentTextResponse(job_id=job.job_id, source="extracted", pages=pages)


@router.get("/jobs/{job_id}/text/redacted", response_model=DocumentTextResponse)
def get_redacted_text(
    job: AuthorizedJobDep,
    object_store: ObjectStoreDep,
) -> DocumentTextResponse:
    if job.status != JobStatus.READY or job.redacted_object_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redacted text is not available for this job yet",
        )

    require_artifact(object_store, job.redacted_object_key, "Redacted document artifact is missing")

    try:
        document = fitz.open(
            stream=object_store.read_bytes(job.redacted_object_key),
            filetype="pdf",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Redacted document text extraction failed",
        ) from exc

    try:
        pages = [
            TextPageResponse(page_number=page.number + 1, text=page.get_text()) for page in document
        ]
    finally:
        document.close()

    return DocumentTextResponse(job_id=job.job_id, source="redacted", pages=pages)
