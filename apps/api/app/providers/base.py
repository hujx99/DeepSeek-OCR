from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class OCRInput:
    file_path: Path
    page_no: int = 1
    mode: str = "general"
    template_type: str | None = None


@dataclass(frozen=True)
class OCRResult:
    text: str
    markdown: str
    structured: dict = field(default_factory=dict)
    confidence_summary: dict = field(default_factory=dict)


class OCRProvider(Protocol):
    def recognize(self, payload: OCRInput) -> OCRResult:
        ...
