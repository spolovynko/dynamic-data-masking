from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from ddm_engine.config import Settings
from ddm_engine.storage.object_store import ObjectStore, create_object_store

READ_CHUNK_BYTES = 1024 * 1024
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".txt": "txt",
}
JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


class JobStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    OCR_RUNNING = "ocr_running"
    DETECTING = "detecting"
    LLM_VALIDATING = "llm_validating"
    PLANNING_REDACTIONS = "planning_redactions"
    REDACTING = "redacting"
    GENERATING_PREVIEWS = "generating_previews"
    VERIFYING = "verifying"
    READY = "ready"
    FAILED = "failed"
    FAILED_VERIFICATION = "failed_verification"
    CANCELLED = "cancelled"


class JobStorageError(Exception):
    """Base exception for job storage failures."""


class UnsupportedFileTypeError(JobStorageError):
    pass


class UploadTooLargeError(JobStorageError):
    pass


class EmptyUploadError(JobStorageError):
    pass


class JobNotFoundError(JobStorageError):
    pass


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    status: JobStatus
    original_filename: str
    original_object_key: str
    file_type: str
    content_type: str | None
    size_bytes: int
    redacted_object_key: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime

    def to_response_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "filename": self.original_filename,
            "file_type": self.file_type,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class JobStore:
    def __init__(
        self,
        object_store: ObjectStore,
        repository: DocumentJobRepository,
        max_upload_bytes: int,
    ) -> None:
        self.object_store = object_store
        self.repository = repository
        self.max_upload_bytes = max_upload_bytes

    @classmethod
    def from_environment(cls) -> JobStore:
        settings = Settings()
        from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository

        return cls(
            object_store=create_object_store(settings),
            repository=SqlAlchemyDocumentJobRepository.from_settings(settings),
            max_upload_bytes=settings.max_upload_bytes,
        )

    async def create_from_upload(self, upload: UploadFile) -> JobRecord:
        original_filename = _clean_filename(upload.filename)
        extension = Path(original_filename).suffix.lower()
        file_type = SUPPORTED_EXTENSIONS.get(extension)
        if file_type is None:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise UnsupportedFileTypeError(f"Unsupported file type. Allowed extensions: {allowed}")

        job_id = uuid4().hex
        original_object_key = f"originals/{job_id}/original{extension}"
        size_bytes = 0

        try:
            with self.object_store.open_writer(original_object_key) as output:
                while chunk := await upload.read(READ_CHUNK_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > self.max_upload_bytes:
                        raise UploadTooLargeError(
                            f"Upload exceeds maximum size of {self.max_upload_bytes} bytes"
                        )
                    output.write(chunk)

            if size_bytes == 0:
                raise EmptyUploadError("Uploaded file is empty")

            timestamp = datetime.now(UTC)
            record = JobRecord(
                job_id=job_id,
                status=JobStatus.UPLOADED,
                original_filename=original_filename,
                original_object_key=original_object_key,
                file_type=file_type,
                content_type=upload.content_type,
                size_bytes=size_bytes,
                redacted_object_key=None,
                failure_reason=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
            return self.repository.create(record)
        except Exception:
            self.object_store.delete(original_object_key)
            raise
        finally:
            await upload.close()

    def get(self, job_id: str) -> JobRecord:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            raise JobNotFoundError(f"Job not found: {job_id}")
        return self.repository.get(job_id)

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        failure_reason: str | None = None,
    ) -> JobRecord:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            raise JobNotFoundError(f"Job not found: {job_id}")
        return self.repository.update_status(job_id, status, failure_reason=failure_reason)


def _clean_filename(filename: str | None) -> str:
    if filename is None:
        raise UnsupportedFileTypeError("Uploaded file must include a filename")

    cleaned = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    if not cleaned:
        raise UnsupportedFileTypeError("Uploaded file must include a filename")
    return cleaned


class DocumentJobRepository:
    def create(self, job: JobRecord) -> JobRecord:
        raise NotImplementedError

    def get(self, job_id: str) -> JobRecord:
        raise NotImplementedError

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        failure_reason: str | None = None,
    ) -> JobRecord:
        raise NotImplementedError
