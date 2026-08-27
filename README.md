# Content Creator — Agentic ETL Platform

Learning-first agentic ETL pipeline: ingest Instagram export data, run a multi-agent LangGraph workflow (Profiler → Engineer → Executor → Validator), and produce a gold-layer taste profile in PostgreSQL.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000/docs |
| Streamlit UI | http://localhost:8501 |
| Postgres | localhost:5432 (`cc` / `cc`) |

## Local setup (without Docker)

Works with an existing Postgres + Redis on your machine.

1. **Create the database**

```bash
createdb -h localhost -U postgres content_creator
# Or: psql -h localhost -U postgres -c "CREATE DATABASE content_creator;"
```

2. **Configure environment**

```bash
cp .env.example .env
# Edit DATABASE_URL, e.g.:
# DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/content_creator
```

3. **Install and run**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
set -a && source ../.env && set +a
export STORAGE_PATH=../storage

# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker (required for async uploads)
celery -A app.tasks.celery_app worker --loglevel=info

# Terminal 3 — Streamlit UI (optional)
streamlit run streamlit_app/app.py
```

## Phase 0 lab (minimal, no UI)

```bash
cd backend && source .venv/bin/activate
set -a && source ../.env && set +a
python lab/minimal_etl_lab.py
```

Runs the full LangGraph pipeline on `sample_data/liked_posts_sample.json` and prints agent logs.

## Upload data

1. **Sample JSON:** `backend/sample_data/liked_posts_sample.json`
2. **Instagram export:** Accounts Center → Export your information → upload the ZIP via Streamlit or API

**API example:**

```bash
curl -X POST "http://localhost:8000/ingest/export?simulate_failure=true" \
  -F "file=@backend/sample_data/liked_posts_sample.json"

# Poll job status (replace JOB_ID)
curl http://localhost:8000/ingest/jobs/JOB_ID

# Approve after pipeline pauses at human review
curl -X POST http://localhost:8000/ingest/jobs/JOB_ID/approve \
  -H "Content-Type: application/json" -d '{"approved": true}'
```

## Agent pipeline

```mermaid
flowchart LR
  Ingestion --> Profiler --> Engineer --> Executor
  Executor -->|failure| Engineer
  Executor --> Validator --> HumanReview
```

Enable **`simulate_failure=true`** (API query param or Streamlit checkbox) to see the Engineer ↔ Executor self-healing loop: Executor fails on silver transform → Engineer revises plan → Executor retries.

## Cloud SQL migration

Use the same `DATABASE_URL` with a Cloud SQL Postgres connection string. Move `STORAGE_PATH` to GCS/S3 for bronze artifacts. No SQLite — schema is Alembic-ready.

## Phase 2 (not implemented yet)

- Instagram Graph API OAuth sync
- Trend Scout + Content Strategist agents
