from app.core.config import get_settings
from app.providers.base import OCRInput, OCRResult


class DeepSeekOCR2Provider:
    """Placeholder for a service-backed DeepSeek-OCR-2 integration.

    The web API and UI depend only on OCRProvider. A production implementation can
    call a vLLM HTTP service or a local transformers worker here without changing
    the rest of the product contract.
    """

    def recognize(self, payload: OCRInput) -> OCRResult:
        settings = get_settings()
        if not settings.deepseek_ocr2_endpoint:
            raise RuntimeError("DEEPSEEK_OCR2_ENDPOINT is required when OCR_PROVIDER=deepseek_ocr2")
        raise NotImplementedError("DeepSeek-OCR-2 service call is intentionally left as an integration point")
