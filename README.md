# Dynamic Data Masking

[![CI/CD](https://github.com/spolovynko/dynamic-data-masking/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/spolovynko/dynamic-data-masking/actions/workflows/ci-cd.yml)

Dynamic Data Masking is a Python/FastAPI document redaction platform. It accepts
PDF, DOCX, TXT, and image uploads, extracts text and coordinates, detects
personal or sensitive data, plans black-box redactions, permanently redacts the
document, verifies that sensitive text is no longer extractable, and serves the
redacted PDF for download.

The project is built as a reusable redaction engine plus thin API and worker
apps, so the engine can also be used from tests, CLIs, or future batch jobs.

## Features

- FastAPI backend with upload, job status, detection, review, redaction plan,
  verification, text preview, metrics, and download endpoints.
- Browser frontend served from the API at `http://127.0.0.1:8000/`.
- Celery worker with Redis queueing.
- PostgreSQL-ready metadata storage with SQLite local fallback.
- Local object storage abstraction for originals, extracted layouts,
  detections, review overrides, plans, verification reports, and redacted PDFs.
- Native PDF text extraction with word-level coordinates through PyMuPDF.
- OCR fallback for scanned PDFs and image uploads through Tesseract/PyMuPDF.
- DOCX and TXT extraction with synthetic layout generation.
- Regex detector for deterministic values such as email, phone, IBAN, credit
  cards, and secrets.
- Presidio detector, intentionally configurable and currently recommended for
  names only.
- Ollama-backed LLM detector for contextual sensitive categories such as health,
  religion, politics, trade union membership, racial or ethnic origin, national
  origin, addresses, criminal history, biometrics, and sexual orientation.
- Human review controls to mask or skip detections before regenerating the
  redacted output.
- Post-redaction verification to catch extractable sensitive text leakage.
- Structured JSON logs, request/correlation IDs, Prometheus metrics, and
  optional Prometheus/Grafana Compose profile.
- Alembic migration scaffold.

## Architecture

```text
browser frontend
    |
    v
FastAPI API ------ PostgreSQL or SQLite metadata
    |                         |
    |                         v
    |                  document_jobs
    |
    +------ local object store
    |       originals/
    |       extracted/
    |       detections/
    |       reviews/
    |       plans/
    |       quality/
    |       redacted/
    |
    v
Redis queue
    |
    v
Celery worker
    |
    +-- extraction: PDF text, OCR, DOCX, TXT
    +-- detection: regex, Presidio, LLM
    +-- planning: merge detections and boxes
    +-- rendering: permanent PDF redaction
    +-- quality: post-redaction verification
```

## Requirements

- Python 3.11+
- uv
- Docker Desktop for the containerized stack
- Redis when running workers locally
- PostgreSQL optional, SQLite is used by default
- Ollama optional, only needed when LLM detection is enabled
- Tesseract optional for local OCR; the Docker image installs it automatically

## Quick Start With Docker

Start API, Redis, and worker:

```powershell
docker compose up -d --build
```

Open the app:

```text
http://127.0.0.1:8000/
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Check health:

```powershell
curl.exe http://127.0.0.1:8000/api/health
```

## Local Development

Install dependencies:

```powershell
uv sync
```

Run the API:

```powershell
uv run ddm-api
```

Run the worker when Redis is available:

```powershell
uv run ddm-worker
```

Run tests and linting:

```powershell
uv run pytest
uv run ruff check .
```

Run migrations:

```powershell
uv run alembic upgrade head
```

## Configuration

Configuration is read from environment variables. See `.env.example`.

Important variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DDM_DATA_ROOT` | Local data root | `data` |
| `DDM_DATABASE_URL` | Metadata DB URL | SQLite under data root |
| `DDM_QUEUE_BROKER_URL` | Celery broker | `redis://localhost:6379/0` |
| `DDM_QUEUE_RESULT_BACKEND` | Celery result backend | `redis://localhost:6379/1` |
| `DDM_PRESIDIO_ENABLED` | Enable Presidio | `false` |
| `DDM_PRESIDIO_ENTITIES` | Presidio entities | `PERSON` |
| `DDM_LLM_ENABLED` | Enable Ollama LLM detector | `false` |
| `DDM_OLLAMA_BASE_URL` | Ollama endpoint | `http://127.0.0.1:11434` |
| `DDM_OLLAMA_MODEL` | Ollama model | `qwen2.5:3b` |
| `DDM_OCR_ENABLED` | Enable OCR fallback | `true` |
| `DDM_OCR_LANGUAGE` | Tesseract language | `eng` |
| `DDM_WORKER_METRICS_PORT` | Worker metrics port | `9101` |

Example PostgreSQL configuration:

```powershell
$env:DDM_DATABASE_URL = "postgresql+psycopg://ddm:ddm@localhost:5432/ddm"
```

When PostgreSQL runs on the Windows host and the app runs in Docker Desktop, use
`host.docker.internal` instead of `localhost`.

## LLM Detection

The LLM is not the redaction engine. It is only a contextual detector for
ambiguous or semantic sensitive data. Deterministic patterns such as email,
phone, IBAN, credit cards, and secrets are handled by regex and do not need the
LLM.

Enable Ollama-backed detection:

```powershell
$env:DDM_LLM_ENABLED = "true"
$env:DDM_OLLAMA_MODEL = "qwen2.5:3b"
$env:DDM_LLM_TIMEOUT_SECONDS = "120"
docker compose up -d --build
```

For Docker Compose, `DDM_OLLAMA_BASE_URL` defaults to
`http://host.docker.internal:11434`, so containers can reach Ollama running on
the Windows host.

## API Endpoints

- `GET /`
- `GET /metrics`
- `GET /api/health`
- `GET /api/metrics`
- `POST /api/documents`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/process`
- `GET /api/jobs/{job_id}/detections`
- `PATCH /api/jobs/{job_id}/detections/{candidate_id}`
- `GET /api/jobs/{job_id}/text/extracted`
- `GET /api/jobs/{job_id}/text/redacted`
- `GET /api/jobs/{job_id}/redaction-plan`
- `POST /api/jobs/{job_id}/redaction-plan/rebuild`
- `GET /api/jobs/{job_id}/verification`
- `GET /api/jobs/{job_id}/download`

The API is authentication-ready through an optional `x-user-id` header. Jobs
uploaded with an owner are only returned to requests with the same owner header.
A real auth provider can replace this dependency later.

## Redaction Workflow

1. User uploads a PDF, DOCX, TXT, or image.
2. API validates and stores the original file.
3. API queues a Celery job.
4. Worker extracts text and word coordinates.
5. OCR runs when needed for scanned PDFs or image uploads.
6. Regex, Presidio, and optional LLM detectors produce candidates.
7. Detection candidates are merged into redaction decisions.
8. Redaction regions are planned from token coordinates.
9. Redaction is permanently applied to a PDF output.
10. The verifier re-extracts text and checks for sensitive-value leakage.
11. The frontend shows extracted text, detections, redacted text, verification
    status, and the download link.

## Object Store Layout

```text
data/objects/originals/{job_id}/original.*
data/objects/extracted/{job_id}/layout.json
data/objects/detections/{job_id}/candidates.json
data/objects/reviews/{job_id}/overrides.json
data/objects/plans/{job_id}/redaction_plan.json
data/objects/quality/{job_id}/verification.json
data/objects/redacted/{job_id}/redacted.pdf
```

## Observability

The API and worker emit structured JSON logs to stdout. API responses include:

- `x-request-id`
- `x-correlation-id`

Prometheus metrics:

```text
http://127.0.0.1:8000/metrics
http://127.0.0.1:8000/api/metrics
http://127.0.0.1:9101/
```

Metrics cover API traffic, uploads, queued jobs, worker duration/failures, OCR,
detection counts, LLM calls/latency/validation failures, redactions, redaction
verification, leakage, and human overrides.

Start Prometheus and Grafana:

```powershell
docker compose --profile observability up -d prometheus grafana
```

Prometheus:

```text
http://127.0.0.1:9090/
```

Grafana:

```text
http://127.0.0.1:3000/
```

## CI/CD

GitHub Actions workflow:

```text
.github/workflows/ci-cd.yml
```

The pipeline runs on pull requests, pushes to `main`, and manual dispatch. It
contains:

- lint and test job: uv sync, Ruff format check, Ruff lint, Pytest
- security job: Bandit source scan and pip-audit dependency audit
- Docker job: Buildx build, API health smoke test, and GHCR image push on `main`
- deployment placeholder: manual `dev`, `staging`, or `prod` gate for future
  environment-specific deployment commands

## Project Structure

```text
frontend/                    browser UI
src/apps/api/                FastAPI app, routes, schemas
src/apps/worker/             Celery worker
src/ddm_engine/extraction/   PDF, OCR, DOCX, TXT extraction
src/ddm_engine/detection/    regex, Presidio, LLM detection
src/ddm_engine/llm/          Ollama client, prompts, schemas, router, safety
src/ddm_engine/planning/     detection merge and redaction planning
src/ddm_engine/rendering/    permanent PDF redaction
src/ddm_engine/quality/      post-redaction verification
src/ddm_engine/storage/      database, object store, repositories
src/ddm_engine/observability/logging, metrics, middleware
tests/                       unit and API tests
migrations/                  Alembic migrations
docker/                      local ops config
```

## Current Limits

- OCR quality depends on the source image and Tesseract language data.
- DOCX/TXT outputs are rendered into a simple synthetic PDF layout for redaction.
- The auth-ready header is not a full authentication system.
- Object storage is local-only today.
- Grafana dashboard JSON is not checked in yet.

## Next Steps

- Add real auth and per-user job listing.
- Add S3-compatible object storage.
- Add richer OCR confidence and visual page previews.
- Add a Grafana dashboard file and alert rules.
- Add CI security checks and Docker image publishing.
- Add manual rectangle drawing in the frontend for custom redactions.
