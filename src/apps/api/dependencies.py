from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from apps.api.auth import RequestActor, assert_job_access, get_request_actor
from ddm_engine.config import Settings
from ddm_engine.storage.jobs import JobNotFoundError, JobRecord, JobStore
from ddm_engine.storage.object_store import ObjectStore, create_object_store
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository


def get_request_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_request_settings)]


def get_object_store(settings: SettingsDep) -> ObjectStore:
    return create_object_store(settings)


ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]


def get_job_store(settings: SettingsDep, object_store: ObjectStoreDep) -> JobStore:
    return JobStore(
        object_store=object_store,
        repository=SqlAlchemyDocumentJobRepository.from_settings(settings),
        max_upload_bytes=settings.max_upload_bytes,
    )


JobStoreDep = Annotated[JobStore, Depends(get_job_store)]
RequestActorDep = Annotated[RequestActor, Depends(get_request_actor)]


def get_authorized_job(
    job_id: str,
    actor: RequestActorDep,
    store: JobStoreDep,
) -> JobRecord:
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    assert_job_access(job, actor)
    return job


AuthorizedJobDep = Annotated[JobRecord, Depends(get_authorized_job)]


def require_artifact(object_store: ObjectStore, key: str, detail: str) -> None:
    if not object_store.exists(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
