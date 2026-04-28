from datetime import UTC, datetime

from ddm_engine.config import Settings
from ddm_engine.storage.jobs import JobRecord, JobStatus
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository


def test_sqlalchemy_job_repository_create_get_and_update(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    settings = Settings()
    repository = SqlAlchemyDocumentJobRepository.from_settings(settings)
    timestamp = datetime.now(UTC)
    job = JobRecord(
        job_id="a" * 32,
        status=JobStatus.UPLOADED,
        original_filename="sample.pdf",
        original_object_key="originals/job/original.pdf",
        file_type="pdf",
        content_type="application/pdf",
        size_bytes=42,
        redacted_object_key=None,
        failure_reason=None,
        created_at=timestamp,
        updated_at=timestamp,
    )

    repository.create(job)
    fetched = repository.get(job.job_id)

    assert fetched.job_id == job.job_id
    assert fetched.original_filename == "sample.pdf"
    assert fetched.original_object_key == "originals/job/original.pdf"

    updated = repository.update_status(
        job.job_id,
        JobStatus.FAILED,
        failure_reason="boom",
    )

    assert updated.status == JobStatus.FAILED
    assert updated.failure_reason == "boom"

    ready = repository.update_redacted_output(
        job.job_id,
        "redacted/job/redacted.pdf",
        JobStatus.READY,
    )

    assert ready.status == JobStatus.READY
    assert ready.redacted_object_key == "redacted/job/redacted.pdf"
    assert ready.failure_reason is None
