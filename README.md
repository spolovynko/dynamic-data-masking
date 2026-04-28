# Dynamic Data Masking

[![CI/CD](https://github.com/spolovynko/dynamic-data-masking/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/spolovynko/dynamic-data-masking/actions/workflows/ci-cd.yml)

Dynamic Data Masking is a Python document redaction platform for finding and permanently hiding sensitive information in uploaded files.

The application accepts documents, extracts their text, detects private or sensitive data, maps each detection back to the document layout, applies black-box redactions, verifies that the sensitive text is no longer extractable, and returns a redacted PDF.

It is built around a reusable redaction engine with a thin FastAPI layer and background worker, so the core document-processing logic can be used from the API, tests, workers, or future command-line tools.

## Why This Project Exists

Many systems can detect sensitive text, and many PDF tools can draw black boxes. A safe redaction platform needs more than that.

This project focuses on the full redaction lifecycle:

- extracting text from native PDFs, images, scanned documents, DOCX, and TXT files
- detecting deterministic PII such as emails, phone numbers, IDs, and secrets
- detecting contextual sensitive data such as health, religion, politics, union membership, nationality, race, sexuality, criminal history, biometrics, and addresses
- mapping detections to page coordinates
- permanently removing sensitive content from the output document
- verifying the redacted file before allowing download
- exposing job progress, extracted text, redacted text, and download state through a browser UI

The goal is not only to identify sensitive data, but to produce a document that is safer to share.

## What It Does

- Upload PDF, DOCX, TXT, or image files through a browser frontend.
- Extract native PDF text with word-level coordinates using PyMuPDF.
- Run OCR fallback for scanned PDFs and image uploads.
- Detect structured personal data with regex-based detectors.
- Use Presidio conservatively for selected PII, currently focused on names.
- Use an Ollama-backed LLM for contextual sensitive categories.
- Merge detector outputs into final redaction decisions.
- Plan redaction boxes from token and page coordinates.
- Permanently redact PDFs instead of only drawing overlays.
- Generate extracted and redacted text views before download.
- Verify that redacted sensitive text is no longer extractable.
- Track jobs, artifacts, metrics, and logs for operational visibility.

## How It Works

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
              +--> Extract text and layout
              +--> Run OCR when needed
              +--> Detect sensitive data
              +--> Ask LLM about contextual cases
              +--> Merge decisions
              +--> Plan redaction boxes
              +--> Apply permanent redaction
              +--> Verify output safety
```

The backend stores metadata in PostgreSQL or SQLite, stores document artifacts in a local object-store abstraction, and runs long document-processing work in a Celery worker.

The LLM is intentionally not the whole redaction engine. It is used as a controlled decision component for semantic cases that deterministic detectors cannot reliably identify. It receives small context windows, returns structured JSON, and its output is validated before being trusted.

## Redaction Workflow

1. A user uploads a document.
2. The API validates the file and stores the original artifact.
3. A background job is queued.
4. The worker extracts text and page layout.
5. OCR runs if the document is scanned or image-based.
6. Regex, Presidio, and LLM detectors produce candidate findings.
7. Candidates are merged into final redaction decisions.
8. The planner maps decisions to page coordinates.
9. The renderer applies permanent black-box redactions.
10. The verifier checks the redacted file for sensitive text leakage.
11. The frontend shows progress, extracted text, redacted text, previews, and download state.

## Technology Stack

- Python 3.11+
- FastAPI
- Celery
- Redis
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

## Project Structure

```text
frontend/                    Browser UI served by FastAPI
src/apps/api/                FastAPI app, routes, schemas, middleware
src/apps/worker/             Celery worker entrypoint
src/ddm_engine/extraction/   PDF, OCR, DOCX, TXT extraction
src/ddm_engine/detection/    Regex, Presidio, LLM detection
src/ddm_engine/llm/          Ollama client, prompts, schemas, safety
src/ddm_engine/planning/     Detection merging and redaction planning
src/ddm_engine/rendering/    Permanent PDF redaction
src/ddm_engine/quality/      Post-redaction verification
src/ddm_engine/storage/      Database, repositories, object storage
src/ddm_engine/observability/Logging, metrics, tracing-ready helpers
tests/                       Unit and API tests
migrations/                  Alembic migrations
docker/                      Prometheus and local ops configuration
```

## Quick Start With Docker

Build and start the API, Redis, and worker:

```powershell
docker compose up -d --build
```

Open the browser app:

```text
http://127.0.0.1:8000/
```

Open API documentation:

```text
http://127.0.0.1:8000/docs
```

Check API health:

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

Run tests and linting:

```powershell
uv run pytest
uv run ruff format --check .
uv run ruff check .
```

Run database migrations:

```powershell
uv run alembic upgrade head
```

## Configuration

Configuration is read from environment variables. See `.env.example` for a local template.

Common variables:

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

When the app runs in Docker Desktop and PostgreSQL runs on the Windows host, use `host.docker.internal` instead of `localhost`.

## LLM Support

The LLM layer helps detect contextual sensitive data that simple pattern matching cannot handle well.

Examples include:

- health conditions and medical history
- religion or philosophical belief
- political affiliation or belief
- trade union membership
- race, ethnicity, nationality, or national origin
- sexuality or sexual orientation
- criminal history
- biometric identifiers
- personal addresses

The LLM receives only small snippets around candidate text or page context. It must return strict structured JSON, and the backend validates that response before merging it into the final redaction decision.

Enable LLM detection with Ollama:

```powershell
$env:DDM_LLM_ENABLED = "true"
$env:DDM_OLLAMA_MODEL = "qwen2.5:3b"
docker compose up -d --build
```

For Docker Compose, the Ollama base URL should point from the container to the host:

```text
http://host.docker.internal:11434
```

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

The API is authentication-ready through an optional `x-user-id` header. A real identity provider can replace this dependency later.

## Observability

The application emits structured JSON logs with request IDs, correlation IDs, job IDs, and processing stages.

Prometheus metrics cover:

- API request duration
- uploaded document count
- queued and completed jobs
- worker duration and failures
- OCR duration and confidence
- detection counts by label and detector
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

The GitHub Actions workflow is defined in:

```text
.github/workflows/ci-cd.yml
```

It runs on pull requests, pushes to `main`, and manual dispatch.

Pipeline stages:

- install dependencies with `uv`
- check formatting with Ruff
- run Ruff linting
- run the test suite
- scan source code with Bandit
- audit dependencies with pip-audit
- build the Docker image
- run an API smoke test
- push the image to GitHub Container Registry on `main`
- provide a manual deploy gate for dev, staging, or production

## Current Status

The project currently supports the core local redaction workflow:

- browser upload
- background processing
- text extraction
- OCR fallback
- regex detection
- conservative Presidio detection
- optional Ollama LLM detection
- review overrides
- permanent PDF redaction
- post-redaction verification
- Docker-based local stack
- CI/CD pipeline

## Known Limits

- OCR accuracy depends on document quality and installed language data.
- DOCX and TXT files are rendered into a simplified PDF layout for redaction.
- Object storage is local-only today.
- The `x-user-id` header is an auth-ready placeholder, not a full authentication system.
- The deployment job is intentionally a placeholder until a target infrastructure is selected.
- Grafana dashboard JSON and alert rules are not checked in yet.

## Roadmap

- Add full authentication and authorization.
- Add S3-compatible object storage.
- Add first-class document preview snapshots.
- Add manual rectangle drawing in the frontend.
- Add Grafana dashboards and alert rules.
- Add production deployment commands to CI/CD.
- Expand fixture-based end-to-end redaction tests.
- Add richer DOCX handling.

## Safety Note

This project is designed to reduce sensitive-data exposure, but no automated redaction system should be trusted blindly for high-risk documents. Verification, review workflows, and careful detector tuning are part of the product design.
