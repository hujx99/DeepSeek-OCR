from app.core.config import get_settings
from app.providers.base import OCRInput, OCRProvider, OCRResult
from app.providers.deepseek_ocr2 import DeepSeekOCR2Provider
from app.providers.mock import MockOCRProvider


def get_ocr_provider() -> OCRProvider:
    provider = get_settings().ocr_provider.lower()
    if provider in {"deepseek", "deepseek_ocr2", "deepseek-ocr-2"}:
        return DeepSeekOCR2Provider()
    return MockOCRProvider()


__all__ = ["OCRInput", "OCRProvider", "OCRResult", "get_ocr_provider"]
