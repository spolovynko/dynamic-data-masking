from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from apps.api.schemas.jobs import JobResponse
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
async def upload_document(file: Annotated[UploadFile, File(...)]) -> JobResponse:
    store = JobStore.from_environment()
    try:
        job = await store.create_from_upload(file)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EmptyUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc

    return JobResponse(**job.to_response_dict())
