import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

from app.core.config import get_settings


ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_upload(file: UploadFile) -> str:
    ext = _extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported media type")
    return ext


def save_upload(file: UploadFile, user_id: str) -> tuple[Path, int, int]:
    settings = get_settings()
    ext = validate_upload(file)
    target_dir = settings.upload_dir / user_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid.uuid4()}.{ext}"

    total = 0
    with target_path.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_upload_bytes:
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
            out.write(chunk)

    page_count = get_page_count(target_path, ext)
    return target_path, total, page_count


def get_page_count(path: Path, ext: str | None = None) -> int:
    suffix = ext or path.suffix.lstrip(".").lower()
    if suffix == "pdf":
        try:
            return max(len(PdfReader(str(path)).pages), 1)
        except Exception:
            return 1
    return 1


def copy_to_export(path: Path, filename: str) -> Path:
    settings = get_settings()
    target = settings.export_dir / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    return target
