from __future__ import annotations

import time
from dataclasses import dataclass

import fitz

from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken, PageLayout
from ddm_engine.observability.metrics import OCR_DURATION_SECONDS, OCR_TOKENS_TOTAL


class OcrUnavailableError(Exception):
    """Raised when OCR cannot run in the current runtime."""


@dataclass(frozen=True)
class OcrSettings:
    language: str = "eng"
    dpi: int = 200


class PyMuPdfOcrExtractor:
    def __init__(self, settings: OcrSettings | None = None) -> None:
        self.settings = settings or OcrSettings()

    def extract(self, job_id: str, document_bytes: bytes, source_file_type: str) -> DocumentLayout:
        started_at = time.perf_counter()
        try:
            with fitz.open(stream=document_bytes, filetype=source_file_type) as document:
                pages = [
                    self._extract_page(page, page_index + 1)
                    for page_index, page in enumerate(document)
                ]
        except Exception as exc:
            OCR_DURATION_SECONDS.labels(source_type=source_file_type, outcome="error").observe(
                time.perf_counter() - started_at
            )
            raise OcrUnavailableError("OCR extraction failed") from exc

        token_count = sum(len(page.tokens) for page in pages)
        OCR_DURATION_SECONDS.labels(source_type=source_file_type, outcome="success").observe(
            time.perf_counter() - started_at
        )
        OCR_TOKENS_TOTAL.labels(source_type=source_file_type).inc(token_count)
        return DocumentLayout(job_id=job_id, source_file_type=source_file_type, pages=pages)

    def _extract_page(self, page: fitz.Page, page_number: int) -> PageLayout:
        text_page = page.get_textpage_ocr(
            language=self.settings.language,
            dpi=self.settings.dpi,
            full=True,
        )
        tokens: list[LayoutToken] = []
        for token_index, word in enumerate(
            page.get_text("words", sort=True, textpage=text_page),
            start=1,
        ):
            x0, y0, x1, y1, text, block_number, line_number, word_number = word
            if not text.strip():
                continue
            tokens.append(
                LayoutToken(
                    token_id=f"p{page_number}-t{token_index}",
                    page_number=page_number,
                    text=text,
                    bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
                    block_number=block_number,
                    line_number=line_number,
                    word_number=word_number,
                    source="ocr",
                    confidence=0.85,
                )
            )

        return PageLayout(
            page_number=page_number,
            width=page.rect.width,
            height=page.rect.height,
            rotation=page.rotation,
            tokens=tokens,
        )
