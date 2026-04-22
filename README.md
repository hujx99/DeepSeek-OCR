# DocFlow OCR

[中文说明](./README.zh-CN.md)

DocFlow OCR is a production-oriented MVP for the workflow:

Upload document/image -> async OCR processing -> review/edit result -> export final output.

The app uses a mock OCR provider by default so the full product flow runs without GPU setup. DeepSeek-OCR-2 is isolated behind the same provider interface and can be enabled later without changing the UI contract.

## Structure

```text
apps/web      Next.js UI
apps/api      FastAPI API, SQLAlchemy models, Alembic migrations
apps/worker   RQ worker for asynchronous OCR jobs
packages      Shared workspace placeholder
storage       Local dev uploads and exports
```

Existing upstream DeepSeek OCR reference code remains under `DeepSeek-OCR-master/`.

## Local Development

1. Create an env file:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up --build
```

3. Open:

```text
Web: http://localhost:3000
API: http://localhost:8000/api/health
```

The API creates tables on startup for local development. Alembic files are included under `apps/api/alembic` for production migration workflows.

## Local Development Without Docker

If `docker` is not installed on your machine, you can run the stack directly on macOS or Linux.

1. Prepare infrastructure:

```bash
brew install postgresql@16 redis node
brew services start postgresql@16
brew services start redis
createdb docflow
```

2. Create the env file:

```bash
cp .env.example .env
```

3. Update `.env` for local processes:

```text
DATABASE_URL=postgresql+psycopg://docflow:docflow@localhost:5432/docflow
REDIS_URL=redis://localhost:6379/0
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
LOCAL_STORAGE_ROOT=./storage
OCR_PROVIDER=mock
```

4. Start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
uvicorn app.main:app --app-dir apps/api --reload
```

5. In another terminal, start the worker:

```bash
source .venv/bin/activate
PYTHONPATH=apps/api rq worker --url redis://localhost:6379/0 ocr
```

6. In another terminal, start the web app:

```bash
cd apps/web
npm install
npm run dev
```

7. Open:

```text
Web: http://localhost:3000
API: http://localhost:8000/api/health
```

## Services

- `web`: Next.js upload, job list, result review, export, history pages.
- `api`: FastAPI endpoints for files, jobs, results, exports, and mock auth.
- `worker`: RQ worker that pulls OCR jobs from Redis.
- `postgres`: Application database.
- `redis`: Queue backend.

## Important Environment Variables

```text
DATABASE_URL=postgresql+psycopg://docflow:docflow@postgres:5432/docflow
REDIS_URL=redis://redis:6379/0
LOCAL_STORAGE_ROOT=/app/storage
OCR_PROVIDER=mock
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

To use a future DeepSeek-OCR-2 service implementation:

```text
OCR_PROVIDER=deepseek_ocr2
DEEPSEEK_OCR2_ENDPOINT=http://your-ocr-service
DEEPSEEK_OCR2_API_KEY=...
```

## API Summary

- `GET /api/health`
- `POST /api/files/upload`
- `GET /api/files/{file_id}/download`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/retry`
- `GET /api/jobs/{job_id}/pages`
- `GET /api/jobs/{job_id}/result`
- `PATCH /api/jobs/{job_id}/result`
- `POST /api/jobs/{job_id}/export`
- `GET /api/exports/{filename}`
- `GET /api/history`

## Demo Fixtures

With Python dependencies installed and `PYTHONPATH=apps/api`, seed one completed demo job:

```bash
PYTHONPATH=apps/api python scripts/seed_demo.py
```

## Notes

- Supported uploads: PDF, PNG, JPG, JPEG, WebP.
- OCR work never runs in the API request thread.
- Raw OCR and reviewed results are stored separately.
- Exports use reviewed content, not raw OCR output.
- Mock auth uses `X-User-Email` when provided, otherwise `MOCK_AUTH_EMAIL`.
