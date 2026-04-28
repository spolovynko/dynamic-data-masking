from dataclasses import dataclass

from ddm_engine.extraction.pdf_text import PdfTextExtractor
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore


@dataclass(frozen=True)
class ExtractionResult:
    layout_object_key: str
    page_count: int
    token_count: int


class ExtractionService:
    def __init__(
        self,
        object_store: ObjectStore,
        pdf_text_extractor: PdfTextExtractor | None = None,
    ) -> None:
        self.object_store = object_store
        self.pdf_text_extractor = pdf_text_extractor or PdfTextExtractor()

    def extract_pdf_layout(self, job: JobRecord) -> ExtractionResult:
        document_bytes = self.object_store.read_bytes(job.original_object_key)
        layout = self.pdf_text_extractor.extract(job.job_id, document_bytes)
        layout_object_key = f"extracted/{job.job_id}/layout.json"

        with self.object_store.open_writer(layout_object_key) as output:
            output.write(layout.model_dump_json(indent=2).encode("utf-8"))

        return ExtractionResult(
            layout_object_key=layout_object_key,
            page_count=len(layout.pages),
            token_count=layout.token_count,
        )
