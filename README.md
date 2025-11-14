# RayPP — RAG FAQ backend

This repository contains a minimal RAG-style FAQ backend built with FastAPI, Qdrant (vector DB), OpenAI (embeddings/chat), PostgreSQL (history), and Redis (cache). The project is containerized with Docker Compose for local development.

## Components
- FastAPI app: `src/main.py`, routes in `src/router/base_route.py`
- Vector DB: Qdrant (client: `qdrant-client`)
- Cache: Redis
- History: PostgreSQL (SQLAlchemy ORM)
- File storage: local `media/` (configurable)

## Prerequisites
- Linux / macOS or Windows WSL
- Docker & Docker Compose v2
- Optional: Python 3.12 and a virtualenv to run tests locally

## Quick local development (virtualenv)
1. Create and activate a virtual environment (optional but recommended):

   python -m venv .venv
   source .venv/bin/activate

2. Install dependencies:

   pip install -r requirements.txt

3. Run tests:

   pytest -q

4. Run the app locally (development):

   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

Open API docs at: http://localhost:8000/api/docs

## Docker Compose (recommended local stack)
A `docker-compose.yml` is provided that runs the app + Postgres + Redis + Qdrant.

1. Build and start the stack:

   docker compose up --build -d

2. By default the entrypoint will run tests inside the container on start. To skip tests set the environment variable `SKIP_TESTS=1` in the `docker-compose.yml` service or your environment.

3. Logs:

   docker compose logs -f app

4. Stop and remove:

   docker compose down -v

## Important environment variables
Set these via an `.env` file or in your environment. Example variables used by `src/core/config.py`:
- POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT
- REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
- QDRANT_HOST, QDRANT_PORT, QDRANT_URL, QDRANT_API_KEY
- OPENAI_API_KEY, OPENAI_MODEL, OPENAI_EMBEDDING_MODEL
- MEDIA_ROOT (default: `media`)
- CACHE_PREFIX (default: `ask`), CACHE_TTL_SECONDS (default: 3600)
- APP_HOST, APP_PORT

The project already reads a `.env` file if present (see `src/core/config.py`).

## Database migrations
This project does not include Alembic migrations by default. For production use create Alembic migrations or run `Base.metadata.create_all(engine)` (not recommended for production).

## Tests
- Unit and integration-style tests live in `tests/`.
- Run them locally with `pytest -q` or inside the container (entrypoint runs pytest unless skipped).

## Troubleshooting
- If imports fail inside the container, ensure Docker built successfully and `requirements.txt` matches Python version.
- For DB connection errors, check `POSTGRES_*` env and that the `postgres` service is healthy.
- If Qdrant or Redis are not reachable, confirm service names/ports in `docker-compose.yml` match `src/core/config.py` defaults.

## Notes & next steps
- Token-aware chunking, alembic migrations, better retry/error handling, and real OpenAI key management are recommended next improvements.

If you need a deployment-ready manifest, CI pipeline, or help adding Alembic migrations — tell me which and I will add it.

# Architecture notes

A high-level overview of the application architecture and runtime data flow:

- FastAPI service
  - Entrypoint: `src/main.py` exposes REST endpoints and OpenAPI docs under `/api`.
  - Routes: main routes implemented in `src/router/base_route.py` (`/api/documents`, `/api/ask`, `/health`).

- File ingestion
  - `POST /api/documents` accepts multipart uploads, saves files locally via `src/helpers/file_saver.FileSaver`, and schedules ingestion with `src/services/ingest.Ingestor` as a background task.
  - Ingestor responsibility: read files, chunk content, compute embeddings (OpenAI), and upsert vectors + payloads into Qdrant.

- Question answering (RAG)
  - `POST /api/ask` computes an embedding for the question, queries Qdrant for nearest documents, builds a prompt from retrieved contexts (`build_prompt`), and calls OpenAI ChatCompletion to produce the answer.
  - Responses are cached in Redis (configurable TTL) and saved to PostgreSQL history via `src/services/history.HistorySaver` (scheduled as a background task to avoid blocking requests).

- Datastores
  - Qdrant: vector store for embeddings and retrieval.
  - Redis: short-term cache for recent answers (keyed by question hash + collection).
  - PostgreSQL: persistent query history using SQLAlchemy ORM (`src/models/query_history.py`).
  - Local filesystem: raw uploaded documents stored under `MEDIA_ROOT`.

- Configuration & secrets
  - Environment-based configuration via `src/core/config.py` (pydantic-settings). Use `.env` or environment variables.

- Background tasks & resilience
  - Long-running or blocking operations (ingestion, history saves) are executed as FastAPI background tasks or offloaded to threads to keep request latency low.
  - External systems (OpenAI, Qdrant, Redis) are wrapped with fallbacks in places to allow local testing without all services present.

- Testing & CI
  - Tests live under `tests/` and include unit and integration-style tests that mock external services.
  - The project is containerized; the container entrypoint can run tests at startup (configurable via `SKIP_TESTS`).

This overview should help when extending the system (token-aware chunking, batching embeddings, Alembic migrations, monitoring, or production hardening).
