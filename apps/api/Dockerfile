FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app/apps/api

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY apps/api /app/apps/api
COPY packages /app/packages

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
