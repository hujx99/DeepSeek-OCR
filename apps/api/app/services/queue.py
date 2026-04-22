from redis import Redis
from rq import Queue

from app.core.config import get_settings


QUEUE_NAME = "ocr"


def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis())


def enqueue_ocr_job(job_id: str) -> None:
    queue = get_queue()
    queue.enqueue("app.worker_tasks.process_job", job_id, job_timeout="30m", result_ttl=3600, failure_ttl=86400)
