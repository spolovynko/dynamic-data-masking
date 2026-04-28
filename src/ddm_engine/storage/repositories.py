from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from ddm_engine.config import Settings
from ddm_engine.storage.database import create_session_factory, init_database
from ddm_engine.storage.jobs import JobNotFoundError, JobRecord, JobStatus
from ddm_engine.storage.models import DocumentJobModel


class DocumentJobRepository(Protocol):
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

    def update_redacted_output(
        self,
        job_id: str,
        redacted_object_key: str,
        status: JobStatus,
    ) -> JobRecord:
        raise NotImplementedError


class SqlAlchemyDocumentJobRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @classmethod
    def from_settings(cls, settings: Settings) -> SqlAlchemyDocumentJobRepository:
        init_database(settings)
        return cls(create_session_factory(settings))

    def create(self, job: JobRecord) -> JobRecord:
        with self.session_factory() as session:
            model = DocumentJobModel(
                job_id=job.job_id,
                status=job.status.value,
                original_filename=job.original_filename,
                original_object_key=job.original_object_key,
                file_type=job.file_type,
                content_type=job.content_type,
                size_bytes=job.size_bytes,
                redacted_object_key=job.redacted_object_key,
                failure_reason=job.failure_reason,
                owner_user_id=job.owner_user_id,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return _job_from_model(model)

    def get(self, job_id: str) -> JobRecord:
        with self.session_factory() as session:
            model = session.get(DocumentJobModel, job_id)
            if model is None:
                raise JobNotFoundError(f"Job not found: {job_id}")
            return _job_from_model(model)

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        failure_reason: str | None = None,
    ) -> JobRecord:
        with self.session_factory() as session:
            model = session.get(DocumentJobModel, job_id)
            if model is None:
                raise JobNotFoundError(f"Job not found: {job_id}")

            model.status = status.value
            model.failure_reason = failure_reason
            model.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(model)
            return _job_from_model(model)

    def update_redacted_output(
        self,
        job_id: str,
        redacted_object_key: str,
        status: JobStatus,
    ) -> JobRecord:
        with self.session_factory() as session:
            model = session.get(DocumentJobModel, job_id)
            if model is None:
                raise JobNotFoundError(f"Job not found: {job_id}")

            model.status = status.value
            model.redacted_object_key = redacted_object_key
            model.failure_reason = None
            model.updated_at = datetime.now(UTC)
            session.commit()
            session.refresh(model)
            return _job_from_model(model)


def _job_from_model(model: DocumentJobModel) -> JobRecord:
    return JobRecord(
        job_id=model.job_id,
        status=JobStatus(model.status),
        original_filename=model.original_filename,
        original_object_key=model.original_object_key,
        file_type=model.file_type,
        content_type=model.content_type,
        size_bytes=model.size_bytes,
        redacted_object_key=model.redacted_object_key,
        failure_reason=model.failure_reason,
        created_at=model.created_at,
        updated_at=model.updated_at,
        owner_user_id=model.owner_user_id,
    )
