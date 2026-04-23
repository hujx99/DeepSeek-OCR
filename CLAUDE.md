# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This is a monorepo for **DocFlow OCR**, an MVP web app that wraps an OCR pipeline (upload → async OCR → review → export). Three runtime services live under `apps/`:

- `apps/api` — FastAPI app (`app.main:app`), SQLAlchemy 2.0 models, Alembic migrations.
- `apps/web` — Next.js 14 (App Router, TypeScript) frontend; npm workspace at repo root.
- `apps/worker` — RQ worker that imports `app.worker_tasks.process_job` from the API package (no separate code, just a Dockerfile + requirements reuse).
- `packages/shared` — placeholder workspace, currently empty.
- `DeepSeek-OCR-master/` — vendored upstream DeepSeek-OCR reference code, **not part of the running app**. Do not edit unless explicitly asked.
- `scripts/seed_demo.py` — seeds one completed demo job; run with `PYTHONPATH=apps/api`.
- `storage/` — local dev volume for `uploads/<user_id>/` and `exports/`.

## Commands

### Docker (preferred)
```bash
cp .env.example .env
docker compose up --build         # postgres + redis + api + worker + web
```
Web at http://localhost:3000, API at http://localhost:8000/api/health.

### Local (no Docker)
Requires `postgresql@16`, `redis`, `node`, and a `.venv` with `apps/api/requirements.txt` installed. Each service in its own terminal:
```bash
# API
uvicorn app.main:app --app-dir apps/api --reload
# Worker (must set PYTHONPATH so `app.worker_tasks` resolves)
PYTHONPATH=apps/api rq worker --url redis://localhost:6379/0 ocr
# Web
cd apps/web && npm install && npm run dev
```
Root `package.json` exposes shortcut scripts: `npm run api:dev`, `npm run worker:dev`, `npm run web:dev`.

### Frontend
```bash
cd apps/web
npm run dev | npm run build | npm run lint   # next dev/build/lint
```
There is no test suite. There is no Python linter configured.

### Migrations
Alembic is configured at `apps/api/alembic/` with `sqlalchemy.url` hardcoded in `alembic.ini` to a local Postgres. For dev, the API also auto-creates tables on startup via `Base.metadata.create_all` in [main.py](apps/api/app/main.py) — Alembic is only needed for production migration workflows.

## Architecture

### Job lifecycle (the central flow)
1. `POST /api/files/upload` → [storage.save_upload](apps/api/app/services/storage.py) writes to `storage/uploads/<user_id>/<uuid>.<ext>` and uses `pypdf` to count PDF pages. Allowed: `pdf, png, jpg, jpeg, webp`; max 50 MB.
2. `POST /api/jobs` creates a `Job` row (status=`queued`) and enqueues via `enqueue_ocr_job` → RQ queue named **`ocr`** on Redis.
3. The worker runs [`app.worker_tasks.process_job`](apps/api/app/worker_tasks.py): it loops page-by-page, calls `provider.recognize(OCRInput(...))`, writes one `PageResult` per page (raw text + reviewed text initialized to raw), updates `progress`, and finally writes a single `StructuredResult` if a template was used. On exception, status flips to `failed` and the exception is re-raised so RQ records the failure.
4. UI polls `/api/jobs/{id}` and `/api/jobs/{id}/result`. Reviewer edits via `PATCH /api/jobs/{id}/result` — this only updates `reviewed_*` columns; raw OCR is immutable.
5. `POST /api/jobs/{id}/export` produces `md`/`txt`/`json`/`xlsx` from **reviewed** content (falls back to raw if reviewed is empty) into `storage/exports/job-<job_id>.<ext>`.

### OCR provider abstraction
`get_ocr_provider()` in [providers/__init__.py](apps/api/app/providers/__init__.py) selects implementation by `OCR_PROVIDER` env (`mock` or `deepseek`/`deepseek_ocr2`/`deepseek-ocr-2`). All providers implement the same `recognize(OCRInput) -> OCRResult` shape from [providers/base.py](apps/api/app/providers/base.py). When adding a new provider:
- Add the class, register it in `get_ocr_provider`, and keep `OCRResult` fields populated (`text`, `markdown`, optional `structured`, `confidence_summary`).
- The worker handles iteration over pages — providers receive one page at a time.

The `DeepSeekOCR2Provider` posts a single page (rendered to PNG for PDFs at 144 DPI) as `multipart/form-data` to a remote service. If `DEEPSEEK_OCR2_ENDPOINT` is a base URL (no path), it tries `/ocr`, `/api/ocr`, `/v1/ocr`, `/predict`, `/infer` in order. The response parser is intentionally tolerant: it walks the JSON tree looking for fields named `text`, `markdown`, `structured`, `confidence`, etc.

### Auth model
**Mock only.** [`get_current_user`](apps/api/app/core/auth.py) reads the `X-User-Email` header (or falls back to `MOCK_AUTH_EMAIL`) and upserts a `User` row. Every route depends on it; ownership checks (`owned_file_or_404`, `owned_job_or_404`) are how multi-tenancy is enforced. Do not assume real auth exists.

### Database
SQLAlchemy 2.0 `Mapped[...]` style models in [models/entities.py](apps/api/app/models/entities.py). JSON columns use `JSON().with_variant(JSONB, "postgresql")` so the schema works against both SQLite (default `database_url` in [config.py](apps/api/app/core/config.py) is `sqlite:///./docflow.db`) and Postgres (Docker setup). Cascades: deleting a `Job` removes its `PageResult`s and `StructuredResult`.

### Frontend ↔ API
The Next.js app is a thin client. All API calls go through [apps/web/lib/api.ts](apps/web/lib/api.ts) using `NEXT_PUBLIC_API_BASE_URL`. CORS allowlist is configured in `Settings.allowed_origins` (comma-separated).

## Conventions

- The repo's working language is mixed English/Chinese; recent commits and `需求文档.md` are Chinese. Match the language of surrounding text/docs when editing.
- Worker code path: imports must be importable as `app.*` (so the worker container sets `PYTHONPATH=/app/apps/api:/app/apps/worker`). Don't introduce relative imports across `apps/api/app/`.
- `OCR_PROVIDER` and `DEEPSEEK_OCR2_*` must be set on **both** `api` and `worker` services — the worker is what actually calls the provider, but the API reads the same settings via `get_settings()` (cached).
- When changing the provider response contract, update `OCRResult` and `process_job` together — `process_job` writes `raw_*` and `reviewed_*` from the same provider output.
