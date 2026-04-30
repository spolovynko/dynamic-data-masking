from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from apps.api.dependencies import JobStoreDep, RequestActorDep
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
    actor: RequestActorDep,
    store: JobStoreDep,
) -> JobResponse:
    return await _upload_document(file, actor.user_id, store)


async def _upload_document(
    file: UploadFile,
    owner_user_id: str | None,
    store: JobStore,
) -> JobResponse:
    try:
        job = await store.create_from_upload_for_owner(file, owner_user_id=owner_user_id)
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
