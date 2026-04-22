import json
import mimetypes
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import fitz

from app.core.config import get_settings
from app.providers.base import OCRInput, OCRResult


class DeepSeekOCR2Provider:
    """Service-backed DeepSeek-OCR-2 integration.

    The provider posts the original upload to a remote OCR endpoint together with
    page and mode metadata. The response parser is intentionally tolerant so the
    app can work with simple custom OCR gateways without changing the rest of the
    product contract.
    """

    request_timeout_seconds = 180
    pdf_render_dpi = 144

    def recognize(self, payload: OCRInput) -> OCRResult:
        settings = get_settings()
        endpoint = (settings.deepseek_ocr2_endpoint or "").strip()
        if not endpoint:
            raise RuntimeError("DEEPSEEK_OCR2_ENDPOINT is required when OCR_PROVIDER=deepseek_ocr2")

        errors: list[str] = []
        for candidate_url in self._candidate_urls(endpoint):
            try:
                return self._request_ocr(
                    candidate_url,
                    payload,
                    api_key=(settings.deepseek_ocr2_api_key or "").strip() or None,
                )
            except Exception as exc:
                errors.append(f"{candidate_url}: {exc}")

        error_message = "; ".join(errors) if errors else "No OCR endpoint candidates were generated"
        raise RuntimeError(f"DeepSeek-OCR-2 request failed. {error_message}")

    def _request_ocr(self, url: str, payload: OCRInput, api_key: str | None) -> OCRResult:
        boundary, body = self._build_multipart_body(payload)
        headers = {
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["X-API-Key"] = api_key
            headers["api-key"] = api_key

        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.request_timeout_seconds) as response:
                raw_body = response.read()
                content_type = response.headers.get("Content-Type", "")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace").strip()
            detail = error_body[:300] if error_body else exc.reason
            raise RuntimeError(f"HTTP {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Connection error: {exc.reason}") from exc

        return self._parse_response(raw_body, content_type=content_type, url=url, page_no=payload.page_no)

    def _parse_response(self, raw_body: bytes, content_type: str, url: str, page_no: int) -> OCRResult:
        body_text = raw_body.decode("utf-8", errors="replace").strip()
        if not body_text:
            raise RuntimeError("Empty response body")

        try:
            response_json = json.loads(body_text)
        except json.JSONDecodeError:
            lowered = body_text.lower()
            if "html" in content_type.lower() or lowered.startswith("<!doctype") or lowered.startswith("<html"):
                raise RuntimeError("Received an HTML page instead of OCR output")
            return OCRResult(
                text=body_text,
                markdown=body_text,
                confidence_summary={
                    "provider": "deepseek_ocr2",
                    "endpoint": url,
                    "response_content_type": content_type or "text/plain",
                },
            )

        candidate_dicts = self._candidate_dicts(response_json, page_no=page_no)
        text = self._first_string(candidate_dicts, "text", "raw_text", "ocr_text", "result_text", "content", "result")
        markdown = self._first_string(candidate_dicts, "markdown", "raw_markdown", "md", "content", "result", "text")
        structured = self._first_dict(candidate_dicts, "structured", "structured_result", "result_json")
        confidence_summary = self._first_dict(candidate_dicts, "confidence_summary", "confidence")

        if not confidence_summary:
            confidence_summary = {}
            overall = self._first_number(candidate_dicts, "overall_confidence", "confidence", "score")
            if overall is not None:
                confidence_summary["overall"] = overall

        confidence_summary.setdefault("provider", "deepseek_ocr2")
        confidence_summary.setdefault("endpoint", url)
        confidence_summary.setdefault("response_content_type", content_type or "application/json")

        if not text and markdown:
            text = markdown
        if not markdown and text:
            markdown = text
        if not text and not markdown:
            raise RuntimeError("JSON response did not include usable OCR text fields")

        return OCRResult(
            text=text,
            markdown=markdown,
            structured=structured or {},
            confidence_summary=confidence_summary,
        )

    def _build_multipart_body(self, payload: OCRInput) -> tuple[str, bytes]:
        boundary = f"DocFlowBoundary{uuid.uuid4().hex}"
        fields: list[tuple[str, str]] = [
            ("page_no", str(payload.page_no)),
            ("page", str(payload.page_no)),
            ("page_number", str(payload.page_no)),
            ("mode", payload.mode),
        ]
        if payload.template_type:
            fields.append(("template_type", payload.template_type))

        filename, mime_type, file_bytes = self._prepare_upload(payload)
        filename = filename.replace('"', "")

        chunks: list[bytes] = []
        for name, value in fields:
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            chunks.append(value.encode("utf-8"))
            chunks.append(b"\r\n")

        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
        chunks.append(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
        chunks.append(file_bytes)
        chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return boundary, b"".join(chunks)

    def _prepare_upload(self, payload: OCRInput) -> tuple[str, str, bytes]:
        suffix = payload.file_path.suffix.lower()
        if suffix != ".pdf":
            filename = payload.file_path.name
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            return filename, mime_type, payload.file_path.read_bytes()

        return self._render_pdf_page(payload.file_path, payload.page_no)

    def _render_pdf_page(self, file_path, page_no: int) -> tuple[str, str, bytes]:
        document = fitz.open(file_path)
        try:
            if page_no < 1 or page_no > document.page_count:
                raise RuntimeError(f"Requested PDF page {page_no} but document has {document.page_count} pages")

            scale = self.pdf_render_dpi / 72
            page = document.load_page(page_no - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            filename = f"{file_path.stem}-page-{page_no}.png"
            return filename, "image/png", pixmap.tobytes("png")
        finally:
            document.close()

    def _candidate_urls(self, endpoint: str) -> list[str]:
        parsed = urlparse(endpoint)
        normalized = endpoint.rstrip("/")
        if parsed.path and parsed.path not in {"", "/"}:
            return [normalized]

        return list(
            dict.fromkeys(
                [
                    normalized,
                    f"{normalized}/ocr",
                    f"{normalized}/api/ocr",
                    f"{normalized}/v1/ocr",
                    f"{normalized}/predict",
                    f"{normalized}/infer",
                ]
            )
        )

    def _candidate_dicts(self, payload: Any, page_no: int) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("pages", "results", "predictions"):
                items = payload.get(key)
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_page = item.get("page_no", item.get("page", item.get("page_number")))
                    if str(item_page) == str(page_no):
                        candidates.append(item)

        queue: list[Any] = [payload]
        while queue:
            current = queue.pop(0)
            if isinstance(current, dict):
                candidates.append(current)
                for value in current.values():
                    if isinstance(value, (dict, list)):
                        queue.append(value)
            elif isinstance(current, list):
                for item in current:
                    if isinstance(item, (dict, list)):
                        queue.append(item)
        return candidates

    @staticmethod
    def _first_string(candidates: list[dict[str, Any]], *keys: str) -> str:
        for candidate in candidates:
            for key in keys:
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _first_dict(candidates: list[dict[str, Any]], *keys: str) -> dict[str, Any]:
        for candidate in candidates:
            for key in keys:
                value = candidate.get(key)
                if isinstance(value, dict):
                    return value
        return {}

    @staticmethod
    def _first_number(candidates: list[dict[str, Any]], *keys: str) -> float | int | None:
        for candidate in candidates:
            for key in keys:
                value = candidate.get(key)
                if isinstance(value, int | float):
                    return value
        return None
