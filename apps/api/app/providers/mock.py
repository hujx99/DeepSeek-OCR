import hashlib

from app.providers.base import OCRInput, OCRResult


class MockOCRProvider:
    def recognize(self, payload: OCRInput) -> OCRResult:
        digest = hashlib.sha256(f"{payload.file_path}:{payload.page_no}:{payload.mode}".encode()).hexdigest()[:10]
        title = payload.file_path.name
        text = (
            f"Mock OCR result for {title}\n"
            f"Page: {payload.page_no}\n"
            f"Mode: {payload.mode}\n"
            f"Reference: {digest}\n\n"
            "This deterministic result lets the review and export workflow run without a GPU."
        )
        markdown = (
            f"# {title} - page {payload.page_no}\n\n"
            f"- Mode: `{payload.mode}`\n"
            f"- Reference: `{digest}`\n\n"
            "This deterministic result lets the review and export workflow run without a GPU.\n"
        )
        structured = {
            "document_name": title,
            "page_no": payload.page_no,
            "mode": payload.mode,
            "reference": digest,
        }
        return OCRResult(
            text=text,
            markdown=markdown,
            structured=structured,
            confidence_summary={"overall": 0.99, "provider": "mock"},
        )
