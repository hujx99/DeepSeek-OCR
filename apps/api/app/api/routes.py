from pathlib import Path

import fitz
from fastapi import APIRouter, Depends, File as UploadFileField, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import File, Job, JobStatus, PageResult, StructuredResult, User
from app.schemas import (
    ExportRequest,
    ExportResponse,
    FileRead,
    JobCreate,
    JobRead,
    JobResultRead,
    PageResultRead,
    ResultUpdate,
)
from app.services.exporter import SUPPORTED_EXPORTS, export_job
from app.services.queue import enqueue_ocr_job
from app.services.storage import save_upload

router = APIRouter(prefix="/api")


def owned_file_or_404(db: Session, user: User, file_id: str) -> File:
    file = db.get(File, file_id)
    if not file or file.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file


def owned_job_or_404(db: Session, user: User, job_id: str) -> Job:
    job = db.scalar(select(Job).options(selectinload(Job.file)).where(Job.id == job_id))
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"id": user.id, "email": user.email}


@router.post("/files/upload", response_model=FileRead)
def upload_file(
    upload: UploadFile = UploadFileField(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> File:
    path, size, page_count = save_upload(upload, user.id)
    file = File(
        user_id=user.id,
        original_name=upload.filename or path.name,
        storage_path=str(path),
        mime_type=upload.content_type or "application/octet-stream",
        file_size=size,
        page_count=page_count,
    )
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    inline: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    file = owned_file_or_404(db, user, file_id)
    return FileResponse(
        file.storage_path,
        media_type=file.mime_type,
        filename=file.original_name,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.get("/files/{file_id}/preview")
def preview_file(
    file_id: str,
    page_no: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    file = owned_file_or_404(db, user, file_id)
    if file.mime_type != "application/pdf":
        return FileResponse(
            file.storage_path,
            media_type=file.mime_type,
            filename=file.original_name,
            content_disposition_type="inline",
        )

    document = fitz.open(file.storage_path)
    try:
        if page_no < 1 or page_no > document.page_count:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF page not found")
        page = document.load_page(page_no - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return Response(content=pixmap.tobytes("png"), media_type="image/png")
    finally:
        document.close()


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Job:
    owned_file_or_404(db, user, payload.file_id)
    job = Job(
        user_id=user.id,
        file_id=payload.file_id,
        mode=payload.mode,
        output_format=payload.output_format,
        template_type=payload.template_type,
        status=JobStatus.queued,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_ocr_job(job.id)
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    status_filter: JobStatus | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Job]:
    stmt = select(Job).options(selectinload(Job.file)).where(Job.user_id == user.id).order_by(Job.created_at.desc())
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if q:
        stmt = stmt.join(Job.file).where(File.original_name.ilike(f"%{q}%"))
    return list(db.scalars(stmt))


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Job:
    return owned_job_or_404(db, user, job_id)


@router.post("/jobs/{job_id}/retry", response_model=JobRead)
def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Job:
    job = owned_job_or_404(db, user, job_id)
    if job.status != JobStatus.failed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed jobs can be retried")
    job.status = JobStatus.queued
    job.progress = 0
    job.error_message = None
    db.commit()
    enqueue_ocr_job(job.id)
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}/pages", response_model=list[PageResultRead])
def get_pages(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PageResult]:
    owned_job_or_404(db, user, job_id)
    return list(db.scalars(select(PageResult).where(PageResult.job_id == job_id).order_by(PageResult.page_no)))


@router.get("/jobs/{job_id}/result", response_model=JobResultRead)
def get_result(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobResultRead:
    job = owned_job_or_404(db, user, job_id)
    pages = list(db.scalars(select(PageResult).where(PageResult.job_id == job_id).order_by(PageResult.page_no)))
    structured = db.scalar(select(StructuredResult).where(StructuredResult.job_id == job_id))
    return JobResultRead(job=job, pages=pages, structured_result=structured)


@router.patch("/jobs/{job_id}/result", response_model=JobResultRead)
def update_result(
    job_id: str,
    payload: ResultUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobResultRead:
    job = owned_job_or_404(db, user, job_id)
    if payload.page_no is not None:
        page = db.scalar(select(PageResult).where(PageResult.job_id == job_id, PageResult.page_no == payload.page_no))
        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page result not found")
        if payload.reviewed_text is not None:
            page.reviewed_text = payload.reviewed_text
        if payload.reviewed_markdown is not None:
            page.reviewed_markdown = payload.reviewed_markdown
        if payload.is_confirmed is not None:
            page.is_confirmed = payload.is_confirmed
    if payload.reviewed_json is not None or (payload.is_confirmed is not None and payload.page_no is None):
        structured = db.scalar(select(StructuredResult).where(StructuredResult.job_id == job_id))
        if not structured:
            structured = StructuredResult(job_id=job_id, template_type=job.template_type, raw_json={}, reviewed_json={})
            db.add(structured)
        if payload.reviewed_json is not None:
            structured.reviewed_json = payload.reviewed_json
        if payload.is_confirmed is not None and payload.page_no is None:
            structured.is_confirmed = payload.is_confirmed
    db.commit()
    return get_result(job_id, db, user)


@router.post("/jobs/{job_id}/export", response_model=ExportResponse)
def create_export(
    job_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExportResponse:
    job = owned_job_or_404(db, user, job_id)
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only completed jobs can be exported")
    if payload.format.lower() not in SUPPORTED_EXPORTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format")
    path = export_job(db, job, payload.format)
    return ExportResponse(format=payload.format, filename=path.name, download_url=f"/api/exports/{path.name}")


@router.get("/exports/{filename}")
def download_export(
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    if not filename.startswith("job-"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    job_id = filename.removeprefix("job-").rsplit(".", 1)[0]
    owned_job_or_404(db, user, job_id)
    path = Path("storage/exports") / filename
    if not path.exists():
        from app.core.config import get_settings

        path = get_settings().export_dir / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return FileResponse(path, filename=filename)


@router.get("/history", response_model=list[JobRead])
def history(
    status_filter: JobStatus | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Job]:
    return list_jobs(status_filter=status_filter, q=q, db=db, user=user)
