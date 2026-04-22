from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import JobStatus


class UserRead(BaseModel):
    id: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class FileRead(BaseModel):
    id: str
    original_name: str
    mime_type: str
    file_size: int
    page_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobCreate(BaseModel):
    file_id: str
    mode: str = "general"
    output_format: str = "markdown"
    template_type: str | None = None


class JobRead(BaseModel):
    id: str
    file_id: str
    mode: str
    output_format: str
    template_type: str | None
    status: JobStatus
    progress: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    file: FileRead | None = None

    model_config = ConfigDict(from_attributes=True)


class PageResultRead(BaseModel):
    id: str
    job_id: str
    page_no: int
    raw_text: str
    raw_markdown: str
    reviewed_text: str
    reviewed_markdown: str
    confidence_summary: dict[str, Any]
    is_confirmed: bool

    model_config = ConfigDict(from_attributes=True)


class StructuredResultRead(BaseModel):
    id: str
    job_id: str
    template_type: str | None
    raw_json: dict[str, Any]
    reviewed_json: dict[str, Any]
    is_confirmed: bool

    model_config = ConfigDict(from_attributes=True)


class JobResultRead(BaseModel):
    job: JobRead
    pages: list[PageResultRead]
    structured_result: StructuredResultRead | None = None


class ResultUpdate(BaseModel):
    page_no: int | None = None
    reviewed_text: str | None = None
    reviewed_markdown: str | None = None
    reviewed_json: dict[str, Any] | None = None
    is_confirmed: bool | None = None


class ExportRequest(BaseModel):
    format: str


class ExportResponse(BaseModel):
    format: str
    filename: str
    download_url: str
