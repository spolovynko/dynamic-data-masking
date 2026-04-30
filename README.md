# Dynamic Data Masking

[![CI/CD](https://github.com/spolovynko/dynamic-data-masking/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/spolovynko/dynamic-data-masking/actions/workflows/ci-cd.yml)

Dynamic Data Masking is a Python/FastAPI document redaction platform. It accepts uploaded documents, extracts their text and layout, detects personal or sensitive information, permanently blacks out the matching content, verifies that the sensitive text is no longer extractable, and returns a redacted PDF.

The project is designed around a reusable redaction engine, a thin API layer, and background workers. That keeps the core document-processing logic testable, reusable, and independent from the web framework.

## Why It Exists

Many tools can find sensitive text. Many PDF tools can draw black rectangles. Safe redaction needs the full workflow:

- read the document, including scanned pages
- detect private and sensitive data
- map detections back to page coordinates
- remove the underlying PDF text, not only cover it visually
- verify that the redacted output no longer leaks sensitive content
- give the user progress, review, and download feedback

This project focuses on producing a safer document, not just a list of detected entities.

## Core Capabilities

- Upload PDF, DOCX, TXT, PNG, JPG, JPEG, TIF, and TIFF files.
- Extract native PDF text and word coordinates with PyMuPDF.
- Run OCR fallback for scanned PDFs and image uploads.
- Detect deterministic PII with regex rules.
- Use Presidio conservatively for selected PII, currently focused on names.
- Use an optional Ollama-backed LLM for contextual sensitive categories.
- Detect sensitive categories such as health, religion, politics, trade union membership, race, nationality, sexuality, criminal history, biometrics, and addresses.
- Convert detections into redaction boxes.
- Apply permanent PDF redactions.
- Verify that sensitive values are no longer extractable.
- Show extracted text, redacted text, job progress, and download state in the frontend.
- Expose structured logs and Prometheus metrics.

## Architecture

```text
Browser Frontend
    |
    v
FastAPI API
    |
    +--> Metadata Database
    +--> Object Storage
    +--> Redis Queue
              |
              v
        Celery Worker
              |
              +--> Text extraction
              +--> OCR fallback
              +--> Regex / Presidio / LLM detection
              +--> Decision merge
              +--> Redaction planning
              +--> Permanent PDF redaction
              +--> Verification
```

The API handles HTTP concerns: uploads, job status, review endpoints, text previews, and downloads.

The worker handles long-running processing: extraction, OCR, detection, redaction, and verification.

The engine contains the reusable domain logic. It is separate from FastAPI so it can be tested directly and reused from other entry points later.

## Redaction Workflow

1. The user uploads a document.
2. The API validates the file, stores the original artifact, and creates a job.
3. The job is queued for background processing.
4. The worker extracts text and layout.
5. OCR runs when native text is missing or the input is image-based.
6. Regex, Presidio, and optional LLM detectors produce candidate findings.
7. The decision merger combines overlapping detections.
8. The planner maps final decisions to page coordinates.
9. The renderer applies permanent black-box redactions.
10. The verifier checks the redacted PDF for sensitive text leakage.
11. The frontend shows extracted text, redacted text, verification state, and download link.

## Project Structure

```text
frontend/                    Browser UI served by FastAPI
src/apps/api/                FastAPI app, routes, schemas, dependencies
src/apps/worker/             Celery worker and processing task
src/ddm_engine/extraction/   PDF, OCR, DOCX, and TXT extraction
src/ddm_engine/detection/    Regex, Presidio, LLM detection, review overrides
src/ddm_engine/llm/          Ollama client, prompts, schemas, safety, validation
src/ddm_engine/planning/     Detection merging and redaction planning
src/ddm_engine/rendering/    Permanent PDF redaction
src/ddm_engine/quality/      Post-redaction verification
src/ddm_engine/storage/      Database, repositories, artifact helpers, object store
src/ddm_engine/observability/Logging, metrics, request context, middleware
tests/                       Unit and API tests
migrations/                  Alembic migrations
docker/                      Local observability configuration
```

## Technology Stack

- Python 3.11+
- FastAPI
- Celery and Redis
- PostgreSQL, with SQLite fallback for local development
- SQLAlchemy and Alembic
- PyMuPDF
- Tesseract OCR
- Presidio Analyzer
- Ollama for local LLM support
- Pydantic and pydantic-settings
- Prometheus metrics
- Docker and Docker Compose
- GitHub Actions CI/CD

## Quick Start With Docker

Build and start the local stack:

```powershell
docker compose up -d --build
```

Open the frontend:

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

Run the worker:

```powershell
uv run ddm-worker
```

Run tests and checks:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Run database migrations:

```powershell
uv run alembic upgrade head
```

## Configuration

Configuration is controlled through environment variables. See `.env.example` for a local template.

| Variable | Purpose | Default |
| --- | --- | --- |
| `DDM_DATA_ROOT` | Local data directory | `data` |
| `DDM_DATABASE_URL` | Metadata database URL | SQLite under `data` |
| `DDM_QUEUE_BROKER_URL` | Celery broker URL | `redis://localhost:6379/0` |
| `DDM_QUEUE_RESULT_BACKEND` | Celery result backend | `redis://localhost:6379/1` |
| `DDM_PRESIDIO_ENABLED` | Enable Presidio detection | `false` |
| `DDM_PRESIDIO_ENTITIES` | Presidio entity list | `PERSON` |
| `DDM_LLM_ENABLED` | Enable LLM detection | `false` |
| `DDM_OLLAMA_BASE_URL` | Ollama API URL | `http://127.0.0.1:11434` |
| `DDM_OLLAMA_MODEL` | Ollama model name | `qwen2.5:3b` |
| `DDM_OCR_ENABLED` | Enable OCR fallback | `true` |
| `DDM_OCR_LANGUAGE` | Tesseract language | `eng` |

Example PostgreSQL URL:

```powershell
$env:DDM_DATABASE_URL = "postgresql+psycopg://ddm:ddm@localhost:5432/ddm"
```

When the app runs in Docker Desktop and PostgreSQL runs on the host machine, use `host.docker.internal` instead of `localhost`.

## LLM Support

The LLM is not the full redaction engine. It is a controlled contextual detector.

The application uses deterministic detectors for high-confidence structured values such as emails, phone numbers, IBAN-like values, credit-card-like values, and secrets. The LLM is used for semantic or ambiguous sensitive data where context matters.

Examples:

- health conditions and medical history
- religion or philosophical belief
- political affiliation or belief
- trade union membership
- race, ethnicity, nationality, or national origin
- sexuality or sexual orientation
- criminal history
- biometric identifiers
- personal addresses

The LLM receives limited context, returns strict structured JSON, and the backend validates the response before merging it into final redaction decisions. It never edits PDFs, chooses file paths, or applies redactions directly.

Enable Ollama-backed detection:

```powershell
$env:DDM_LLM_ENABLED = "true"
$env:DDM_OLLAMA_MODEL = "qwen2.5:3b"
docker compose up -d --build
```

For Docker Compose, point the app container to Ollama on the host:

```text
http://host.docker.internal:11434
```

For production-style deployments, run Ollama as a separate service or server with a persistent model volume. The application image does not include the Ollama model.

## API Overview

Main endpoints:

- `GET /`
- `GET /api/health`
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
- `GET /metrics`

The API is authentication-ready through an optional `x-user-id` header. A real authentication provider can replace this dependency later.

## Observability

The API and worker emit structured JSON logs with request IDs, correlation IDs, job IDs, and processing stages.

Prometheus metrics cover:

- API request duration
- upload count
- queued and completed jobs
- worker duration and failures
- OCR duration and confidence
- entity detections by label and detector
- LLM calls, latency, and validation failures
- redactions applied
- verification failures and leakage checks
- human review overrides

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

The GitHub Actions pipeline is defined in:

```text
.github/workflows/ci-cd.yml
```

It runs on pull requests, pushes to `main`, and manual dispatch.

Pipeline stages:

- install dependencies with `uv`
- check formatting with Ruff
- run Ruff linting
- run tests with Pytest
- run Bandit security checks
- run pip-audit dependency checks
- build the Docker image
- run an API health smoke test
- push the image to GitHub Container Registry on `main`
- provide manual dev, staging, and production deployment gates

## Current Status

The project currently supports the local end-to-end MVP:

- document upload
- background processing
- text extraction
- OCR fallback
- regex detection
- conservative Presidio detection
- optional Ollama LLM detection
- detection review overrides
- permanent PDF redaction
- post-redaction verification
- Docker-based local stack
- CI/CD pipeline

## Known Limits

- OCR quality depends on input image quality and installed Tesseract language data.
- DOCX and TXT files are rendered into a simplified PDF layout for redaction.
- Object storage is local-only today.
- The `x-user-id` header is an auth-ready placeholder, not a complete authentication system.
- The deployment job is a placeholder until target infrastructure is selected.
- Grafana dashboard JSON and alert rules are not checked in yet.

## Roadmap

- Add full authentication and authorization.
- Add S3 or Azure Blob artifact storage.
- Add first-class page snapshot previews.
- Add manual rectangle redaction in the frontend.
- Add Grafana dashboards and alert rules.
- Add production deployment commands to CI/CD.
- Expand fixture-based end-to-end redaction tests.
- Add richer DOCX handling.

## Safety Note

This project is designed to reduce sensitive-data exposure, but automated redaction should not be trusted blindly for high-risk documents. Verification, review workflows, strict LLM boundaries, and careful detector tuning are part of the product design.
