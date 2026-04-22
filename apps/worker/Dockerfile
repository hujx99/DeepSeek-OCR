FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/apps/api:/app/apps/worker

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker
COPY packages /app/packages

CMD ["sh", "-c", "rq worker --url \"$REDIS_URL\" ocr"]
