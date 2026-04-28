from __future__ import annotations

import fitz

from ddm_engine.extraction.models import DocumentLayout


def render_layout_to_pdf_bytes(layout: DocumentLayout) -> bytes:
    document = fitz.open()
    try:
        for page_layout in layout.pages:
            page = document.new_page(width=page_layout.width, height=page_layout.height)
            for token in page_layout.tokens:
                page.insert_text(
                    (token.bbox.x0, token.bbox.y1),
                    token.text,
                    fontsize=max(6.0, min(12.0, token.bbox.y1 - token.bbox.y0)),
                    color=(0, 0, 0),
                )
        return document.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        document.close()
