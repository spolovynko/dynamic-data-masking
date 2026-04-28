from typing import Annotated

import fitz
from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth import RequestActor, assert_job_access, get_request_actor
from apps.api.schemas.texts import DocumentTextResponse, TextPageResponse
from ddm_engine.config import Settings
from ddm_engine.detection.text_index import build_page_text_indexes
from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.storage.jobs import JobNotFoundError, JobStatus, JobStore
from ddm_engine.storage.object_store import create_object_store

router = APIRouter(tags=["document-text"])


@router.get("/jobs/{job_id}/text/extracted", response_model=DocumentTextResponse)
def get_extracted_text(
    job_id: str,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> DocumentTextResponse:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    object_store = create_object_store(Settings())
    layout_key = f"extracted/{job_id}/layout.json"
    if not object_store.exists(layout_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted text is not available for this job yet",
        )

    layout = DocumentLayout.model_validate_json(object_store.read_bytes(layout_key))
    pages = [
        TextPageResponse(page_number=index.page_number, text=index.text)
        for index in build_page_text_indexes(layout)
    ]
    return DocumentTextResponse(job_id=job_id, source="extracted", pages=pages)


@router.get("/jobs/{job_id}/text/redacted", response_model=DocumentTextResponse)
def get_redacted_text(
    job_id: str,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> DocumentTextResponse:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    if job.status != JobStatus.READY or job.redacted_object_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redacted text is not available for this job yet",
        )

    object_store = create_object_store(Settings())
    if not object_store.exists(job.redacted_object_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redacted document artifact is missing",
        )

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
            TextPageResponse(page_number=page.number + 1, text=page.get_text())
            for page in document
        ]
    finally:
        document.close()

    return DocumentTextResponse(job_id=job_id, source="redacted", pages=pages)
