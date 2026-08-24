# Deployment

## Local (Docker Compose)

From the repository root:

```bash
docker compose up --build
```

or `make up`.

Compose starts PostgreSQL, Redis, MinIO, Qdrant, runs Alembic, then the API and Celery worker. The API/worker image includes Tesseract and Poppler so scanned PDFs can be OCR'd when digital text is insufficient.

### Acceptance

1. `docker compose ps` shows `api` healthy (or at least running).
2. `curl http://localhost:8000/health` returns `{"status":"ok",...}`.
3. `curl http://localhost:8000/api/v1/health/ready` returns `"status": "ok"` once dependencies are up.
4. MinIO console is at http://localhost:9001.
5. OpenAPI is at http://localhost:8000/docs.

### Stopping

```bash
docker compose down
```

Volumes (`postgres_data`, `redis_data`, `minio_data`, `qdrant_data`) persist until `docker compose down -v`.

## Migrations

Schema is applied only through Alembic:

```bash
docker compose run --rm migrate
```

The API **does not** call `Base.metadata.create_all()` on startup.

## Host-side backend (optional)

With infrastructure already up via Compose, you can run the API on the host:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env   # hosts are localhost, matching published ports
uvicorn app.main:app --reload --port 8000
celery -A app.workers.celery_app:celery_app worker -Q default,ingestion,embedding,indexing
```

## CI

GitHub Actions (`.github/workflows/ci.yml`):

1. Ruff
2. mypy
3. unit tests
4. Docker image build

Integration tests run against Compose-published ports when those services are reachable:

```bash
cd backend && pytest tests/integration -q
```

## Production notes (later)

- Replace Compose defaults (`SECRET_KEY`, MinIO root, Postgres password).
- Point `S3_ENDPOINT_URL` at real S3 or a locked-down MinIO.
- Give Qdrant an API key.
- Run multiple Celery workers per queue.
- Do not expose MinIO console or Postgres ports publicly.
- Frontend (Phase 12) will sit behind the same origin or a configured CORS list.
