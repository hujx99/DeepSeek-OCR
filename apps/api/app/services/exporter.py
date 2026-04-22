import json
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job, PageResult, StructuredResult


SUPPORTED_EXPORTS = {"markdown": "md", "md": "md", "txt": "txt", "json": "json", "xlsx": "xlsx"}


def _reviewed_markdown(page: PageResult) -> str:
    return page.reviewed_markdown or page.raw_markdown or page.reviewed_text or page.raw_text


def _reviewed_text(page: PageResult) -> str:
    return page.reviewed_text or page.raw_text or page.reviewed_markdown or page.raw_markdown


def export_job(db: Session, job: Job, export_format: str) -> Path:
    fmt = export_format.lower()
    if fmt not in SUPPORTED_EXPORTS:
        raise ValueError("Unsupported export format")

    extension = SUPPORTED_EXPORTS[fmt]
    filename = f"job-{job.id}.{extension}"
    path = get_settings().export_dir / filename
    pages = list(db.scalars(select(PageResult).where(PageResult.job_id == job.id).order_by(PageResult.page_no)))
    structured = db.scalar(select(StructuredResult).where(StructuredResult.job_id == job.id))

    if extension == "md":
        path.write_text("\n\n---\n\n".join(_reviewed_markdown(page) for page in pages), encoding="utf-8")
    elif extension == "txt":
        path.write_text("\n\n".join(_reviewed_text(page) for page in pages), encoding="utf-8")
    elif extension == "json":
        payload = {
            "job_id": job.id,
            "mode": job.mode,
            "pages": [
                {
                    "page_no": page.page_no,
                    "text": _reviewed_text(page),
                    "markdown": _reviewed_markdown(page),
                    "confirmed": page.is_confirmed,
                    "confidence_summary": page.confidence_summary,
                }
                for page in pages
            ],
            "structured_result": structured.reviewed_json if structured else None,
            "structured_confirmed": structured.is_confirmed if structured else False,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    elif extension == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "OCR Results"
        sheet.append(["Page", "Confirmed", "Reviewed Text", "Reviewed Markdown"])
        for page in pages:
            sheet.append([page.page_no, page.is_confirmed, _reviewed_text(page), _reviewed_markdown(page)])
        if structured:
            meta = workbook.create_sheet("Structured")
            meta.append(["Field", "Value"])
            for key, value in structured.reviewed_json.items():
                meta.append([key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value])
        workbook.save(path)
    return path
