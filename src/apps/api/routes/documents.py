from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from apps.api.auth import RequestActor, get_request_actor
from apps.api.schemas.jobs import JobResponse
from ddm_engine.observability.metrics import UPLOADED_DOCUMENTS_TOTAL
from ddm_engine.storage.jobs import (
    EmptyUploadError,
    JobStore,
    UnsupportedFileTypeError,
    UploadTooLargeError,
)

router = APIRouter(tags=["documents"])


@router.post(
    "/documents",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> JobResponse:
    return await _upload_document(file, actor)


async def _upload_document(file: UploadFile, actor: RequestActor) -> JobResponse:
    store = JobStore.from_environment()
    try:
        job = await store.create_from_upload_for_owner(file, owner_user_id=actor.user_id)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EmptyUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc

    UPLOADED_DOCUMENTS_TOTAL.labels(file_type=job.file_type).inc()
    return JobResponse(**job.to_response_dict())
