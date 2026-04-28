from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/health",
        headers={"x-request-id": "request-1", "x-correlation-id": "correlation-1"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-1"
    assert response.headers["x-correlation-id"] == "correlation-1"
    assert response.json() == {
        "status": "ok",
        "service": "dynamic-data-masking",
        "version": "0.1.0",
        "environment": "local",
    }


def test_frontend_index_is_served() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Dynamic Data Masking" in response.text


def test_metrics_endpoint_is_served() -> None:
    client = TestClient(create_app())
    client.get("/api/health")

    response = client.get("/api/metrics")
    root_response = client.get("/metrics")

    assert response.status_code == 200
    assert "ddm_api_requests_total" in response.text
    assert "ddm_api_request_duration_seconds" in response.text
    assert root_response.status_code == 200
