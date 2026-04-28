from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.queue import EnqueuedTask


def test_upload_document_creates_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.post(
        "/api/documents",
        files={"file": ("sample.txt", b"hello Jane Doe", "text/plain")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "uploaded"
    assert payload["filename"] == "sample.txt"
    assert payload["file_type"] == "txt"
    assert payload["content_type"] == "text/plain"
    assert payload["size_bytes"] == len(b"hello Jane Doe")

    job_id = payload["job_id"]
    object_path = tmp_path / "objects" / "originals" / job_id / "original.txt"
    assert object_path.read_bytes() == b"hello Jane Doe"
    assert (tmp_path / "metadata.sqlite3").exists()


def test_get_job_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "uploaded"
    assert payload["filename"] == "sample.pdf"
    assert payload["file_type"] == "pdf"


def test_process_job_marks_job_queued_and_returns_task_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "apps.api.queue.enqueue_document_processing_job",
        lambda job_id: EnqueuedTask(task_id=f"task-{job_id}"),
    )
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.post(f"/api/jobs/{job_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "queued"
    assert payload["task_id"] == f"task-{job_id}"

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.json()["status"] == "queued"


def test_process_job_reverts_status_when_enqueue_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))

    def raise_enqueue_error(job_id: str) -> EnqueuedTask:
        raise RuntimeError(f"broker unavailable for {job_id}")

    monkeypatch.setattr("apps.api.queue.enqueue_document_processing_job", raise_enqueue_error)
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.post(f"/api/jobs/{job_id}/process")

    assert response.status_code == 503
    assert response.json()["detail"] == "Failed to enqueue background job"

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.json()["status"] == "uploaded"


def test_upload_rejects_unsupported_file_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.post(
        "/api/documents",
        files={"file": ("image.png", b"not a document", "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported file type. Allowed extensions: .pdf, .txt"


def test_upload_rejects_oversized_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DDM_MAX_UPLOAD_BYTES", "4")
    client = TestClient(create_app())

    response = client.post(
        "/api/documents",
        files={"file": ("large.txt", b"12345", "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Upload exceeds maximum size of 4 bytes"
    object_root = tmp_path / "objects" / "originals"
    assert not object_root.exists() or not any(object_root.rglob("*"))


def test_get_job_returns_404_for_unknown_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.get("/api/jobs/00000000000000000000000000000000")

    assert response.status_code == 404
