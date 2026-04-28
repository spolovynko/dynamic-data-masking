from pydantic import BaseModel


class JobResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    file_type: str
    content_type: str | None
    size_bytes: int
    created_at: str
    updated_at: str


class JobEnqueueResponse(JobResponse):
    task_id: str
