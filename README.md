# dynamic-data-masking

Engine for dynamically masking personal and sensitive data in documents.

## Development

Create the environment and install dependencies:

```powershell
uv sync
```

Run the API locally:

```powershell
uv run ddm-api
```

Run the worker locally when Redis is available:

```powershell
uv run ddm-worker
```

If port `8000` is busy:

```powershell
$env:DDM_API_PORT = "8001"; uv run ddm-api
```

Run tests:

```powershell
uv run pytest
```

## Project foundation

The current foundation uses:

- `apps/api` for the FastAPI application entrypoint and HTTP routes
- `ddm_engine` for reusable engine code, configuration, and future redaction modules
- `uv` for dependency management and reproducible installs
- Docker for the API runtime image

Configuration is provided through environment variables. See `.env.example`.

Local development defaults to:

- SQLite metadata at `data/metadata.sqlite3`
- local object storage under `data/objects`
- PostgreSQL-ready metadata via `DDM_DATABASE_URL`
- Redis/Celery queueing via `DDM_QUEUE_BROKER_URL`

Example PostgreSQL metadata configuration:

```powershell
$env:DDM_DATABASE_URL = "postgresql+psycopg://ddm:ddm@localhost:5432/ddm"
```

## Docker

Build the API image:

```powershell
docker build -t dynamic-data-masking:dev .
```

Run the API container:

```powershell
docker run --rm -p 8000:8000 dynamic-data-masking:dev
```

If local port `8000` is busy:

```powershell
docker run --rm -p 8001:8000 dynamic-data-masking:dev
```

Run API, Redis, and worker together:

```powershell
docker compose up --build
```

The initial API exposes:

- `GET /api/health`
- `POST /api/documents`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/process`

Uploaded files are stored locally under `data/jobs/` by default. Override with:

```powershell
$env:DDM_DATA_ROOT = "C:\path\to\data"; uv run ddm-api
```
