from __future__ import annotations

import fitz

from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken, PageLayout


class ExtractionError(Exception):
    """Raised when document text/layout extraction fails."""


class PdfTextExtractor:
    def extract(self, job_id: str, document_bytes: bytes) -> DocumentLayout:
        try:
            with fitz.open(stream=document_bytes, filetype="pdf") as document:
                pages = [
                    self._extract_page(page, page_index + 1)
                    for page_index, page in enumerate(document)
                ]
        except Exception as exc:
            raise ExtractionError("Failed to extract PDF text layout") from exc

        return DocumentLayout(job_id=job_id, source_file_type="pdf", pages=pages)

    def _extract_page(self, page: fitz.Page, page_number: int) -> PageLayout:
        tokens: list[LayoutToken] = []
        for token_index, word in enumerate(page.get_text("words", sort=True), start=1):
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
                    source="pdf_text",
                    confidence=1.0,
                )
            )

        return PageLayout(
            page_number=page_number,
            width=page.rect.width,
            height=page.rect.height,
            rotation=page.rotation,
            tokens=tokens,
        )
