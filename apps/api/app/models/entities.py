from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.session import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    uploaded = "uploaded"
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    files = relationship("File", back_populates="user")
    jobs = relationship("Job", back_populates="user")


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(String(1024))
    mime_type: Mapped[str] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="files")
    jobs = relationship("Job", back_populates="file")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    mode: Mapped[str] = mapped_column(String(64), default="general")
    output_format: Mapped[str] = mapped_column(String(32), default="markdown")
    template_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.uploaded, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="jobs")
    file = relationship("File", back_populates="jobs")
    page_results = relationship("PageResult", back_populates="job", cascade="all, delete-orphan")
    structured_result = relationship("StructuredResult", back_populates="job", cascade="all, delete-orphan", uselist=False)


class PageResult(Base):
    __tablename__ = "page_results"
    __table_args__ = (UniqueConstraint("job_id", "page_no", name="uq_page_result_job_page"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    raw_markdown: Mapped[str] = mapped_column(Text, default="")
    reviewed_text: Mapped[str] = mapped_column(Text, default="")
    reviewed_markdown: Mapped[str] = mapped_column(Text, default="")
    confidence_summary: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    job = relationship("Job", back_populates="page_results")


class StructuredResult(Base):
    __tablename__ = "structured_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True, index=True)
    template_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    reviewed_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    job = relationship("Job", back_populates="structured_result")
