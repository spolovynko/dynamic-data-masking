from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from ddm_engine.storage.jobs import JobRecord


@dataclass(frozen=True)
class RequestActor:
    user_id: str | None = None


def get_request_actor(x_user_id: str | None = Header(default=None)) -> RequestActor:
    return RequestActor(user_id=x_user_id.strip() if x_user_id else None)


def assert_job_access(job: JobRecord, actor: RequestActor) -> None:
    if job.owner_user_id is None:
        return
    if actor.user_id == job.owner_user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job not found: {job.job_id}",
    )
