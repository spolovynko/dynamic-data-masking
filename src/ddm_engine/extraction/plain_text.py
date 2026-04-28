from __future__ import annotations

from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.extraction.text_layout import TextLayoutBuilder


class PlainTextExtractor:
    def __init__(self, layout_builder: TextLayoutBuilder | None = None) -> None:
        self.layout_builder = layout_builder or TextLayoutBuilder()

    def extract(self, job_id: str, document_bytes: bytes) -> DocumentLayout:
        text = document_bytes.decode("utf-8", errors="replace")
        return self.layout_builder.build(job_id, "txt", text)
