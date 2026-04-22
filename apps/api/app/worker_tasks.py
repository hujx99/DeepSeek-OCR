from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models import Job, JobStatus, PageResult, StructuredResult
from app.providers import OCRInput, get_ocr_provider


def process_job(job_id: str) -> None:
    provider = get_ocr_provider()
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job or job.status == JobStatus.canceled:
            return
        job.status = JobStatus.processing
        job.progress = 1
        job.error_message = None
        db.commit()

        try:
            file = job.file
            total_pages = max(file.page_count or 1, 1)
            db.execute(delete(PageResult).where(PageResult.job_id == job.id))
            db.execute(delete(StructuredResult).where(StructuredResult.job_id == job.id))
            db.commit()

            merged_structured: dict = {}
            for page_no in range(1, total_pages + 1):
                result = provider.recognize(
                    OCRInput(
                        file_path=Path(file.storage_path),
                        page_no=page_no,
                        mode=job.mode,
                        template_type=job.template_type,
                    )
                )
                db.add(
                    PageResult(
                        job_id=job.id,
                        page_no=page_no,
                        raw_text=result.text,
                        raw_markdown=result.markdown,
                        reviewed_text=result.text,
                        reviewed_markdown=result.markdown,
                        confidence_summary=result.confidence_summary,
                    )
                )
                if result.structured:
                    merged_structured[f"page_{page_no}"] = result.structured
                job.progress = int((page_no / total_pages) * 95)
                db.commit()

            if job.template_type or merged_structured:
                db.add(
                    StructuredResult(
                        job_id=job.id,
                        template_type=job.template_type,
                        raw_json=merged_structured,
                        reviewed_json=merged_structured,
                    )
                )
            job.status = JobStatus.completed
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            job = db.get(Job, job_id)
            if job:
                job.status = JobStatus.failed
                job.error_message = str(exc)
                db.commit()
            raise
