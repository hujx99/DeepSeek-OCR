# DocFlow OCR

[English README](./README.md)

DocFlow OCR 是一个面向生产落地的 OCR Web MVP，核心流程是：

上传文档或图片 -> 异步 OCR 处理 -> 在线校对编辑 -> 导出最终结果。

项目默认使用 `mock` OCR provider，因此不需要 GPU 也能跑通完整流程。`DeepSeek-OCR-2` 通过统一的 provider 接口接入，后续切换真实服务时不需要改前端交互协议。

## 目录结构

```text
apps/web      Next.js 前端界面
apps/api      FastAPI 后端 API、SQLAlchemy 模型、Alembic 迁移
apps/worker   基于 RQ 的异步 OCR Worker
packages      预留的共享包目录
storage       本地开发环境的上传文件和导出文件
```

上游 DeepSeek OCR 参考代码保留在 `DeepSeek-OCR-master/` 目录下。

## 本地开发

1. 创建环境变量文件：

```bash
cp .env.example .env
```

2. 启动整套服务：

```bash
docker compose up --build
```

3. 打开以下地址：

```text
Web: http://localhost:3000
API: http://localhost:8000/api/health
```

为了便于本地开发，API 启动时会自动建表。生产环境建议使用 `apps/api/alembic` 下的 Alembic 迁移流程来管理数据库结构。

## 不使用 Docker 的本地启动

如果你的机器上没有安装 `docker`，可以直接在 macOS 或 Linux 上把服务跑起来。

1. 先准备基础依赖：

```bash
brew install postgresql@16 redis node
brew services start postgresql@16
brew services start redis
createdb docflow
```

2. 创建环境变量文件：

```bash
cp .env.example .env
```

3. 把 `.env` 改成本地进程可用的配置：

```text
DATABASE_URL=postgresql+psycopg://docflow:docflow@localhost:5432/docflow
REDIS_URL=redis://localhost:6379/0
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
LOCAL_STORAGE_ROOT=./storage
OCR_PROVIDER=mock
```

4. 启动 API：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
uvicorn app.main:app --app-dir apps/api --reload
```

5. 新开一个终端，启动 worker：

```bash
source .venv/bin/activate
PYTHONPATH=apps/api rq worker --url redis://localhost:6379/0 ocr
```

6. 再开一个终端，启动前端：

```bash
cd apps/web
npm install
npm run dev
```

7. 打开：

```text
Web: http://localhost:3000
API: http://localhost:8000/api/health
```

## 服务说明

- `web`：Next.js 前端，包含上传页、任务页、结果校对页、导出和历史记录页。
- `api`：FastAPI 后端，提供文件上传、任务管理、结果读取与更新、导出、基础 mock 认证等接口。
- `worker`：RQ Worker，从 Redis 队列中拉取 OCR 任务并异步执行。
- `postgres`：应用数据库。
- `redis`：任务队列后端。

## 重要环境变量

```text
DATABASE_URL=postgresql+psycopg://docflow:docflow@postgres:5432/docflow
REDIS_URL=redis://redis:6379/0
LOCAL_STORAGE_ROOT=/app/storage
OCR_PROVIDER=mock
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

后续接入真实 DeepSeek-OCR-2 服务时，可以使用：

```text
OCR_PROVIDER=deepseek_ocr2
DEEPSEEK_OCR2_ENDPOINT=http://your-ocr-service
DEEPSEEK_OCR2_API_KEY=...
```

## API 概览

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

## Demo 数据

在已经安装 Python 依赖、并设置 `PYTHONPATH=apps/api` 的前提下，可以写入一条已完成的演示任务：

```bash
PYTHONPATH=apps/api python3 scripts/seed_demo.py
```

## 说明

- 支持上传的文件类型：PDF、PNG、JPG、JPEG、WebP。
- OCR 处理不会在 API 请求线程里直接执行。
- 原始 OCR 结果和人工修订结果分开存储。
- 导出内容基于用户修订后的结果，而不是原始 OCR 文本。
- mock 认证优先读取请求头 `X-User-Email`，否则回退到 `MOCK_AUTH_EMAIL`。
