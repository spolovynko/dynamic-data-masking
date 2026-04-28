from dataclasses import dataclass

from ddm_engine.config import Settings
from ddm_engine.extraction.docx_text import DocxTextExtractor
from ddm_engine.extraction.ocr import OcrSettings, OcrUnavailableError, PyMuPdfOcrExtractor
from ddm_engine.extraction.pdf_text import PdfTextExtractor
from ddm_engine.extraction.plain_text import PlainTextExtractor
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
        plain_text_extractor: PlainTextExtractor | None = None,
        docx_text_extractor: DocxTextExtractor | None = None,
        ocr_extractor: PyMuPdfOcrExtractor | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.object_store = object_store
        self.pdf_text_extractor = pdf_text_extractor or PdfTextExtractor()
        self.plain_text_extractor = plain_text_extractor or PlainTextExtractor()
        self.docx_text_extractor = docx_text_extractor or DocxTextExtractor()
        self.ocr_extractor = ocr_extractor or PyMuPdfOcrExtractor(
            OcrSettings(
                language=self.settings.ocr_language,
                dpi=self.settings.ocr_dpi,
            )
        )

    def extract_layout(self, job: JobRecord) -> ExtractionResult:
        document_bytes = self.object_store.read_bytes(job.original_object_key)
        if job.file_type == "pdf":
            layout = self.pdf_text_extractor.extract(job.job_id, document_bytes)
            if (
                self.settings.ocr_enabled
                and layout.token_count < self.settings.ocr_min_native_tokens
            ):
                try:
                    layout = self.ocr_extractor.extract(job.job_id, document_bytes, "pdf")
                except OcrUnavailableError:
                    pass
        elif job.file_type == "txt":
            layout = self.plain_text_extractor.extract(job.job_id, document_bytes)
        elif job.file_type == "docx":
            layout = self.docx_text_extractor.extract(job.job_id, document_bytes)
        elif job.file_type in {"png", "jpg", "jpeg", "tif", "tiff"}:
            layout = self.ocr_extractor.extract(job.job_id, document_bytes, job.file_type)
        else:
            raise ValueError(f"Unsupported extraction file type: {job.file_type}")

        layout_object_key = f"extracted/{job.job_id}/layout.json"

        with self.object_store.open_writer(layout_object_key) as output:
            output.write(layout.model_dump_json(indent=2).encode("utf-8"))

        return ExtractionResult(
            layout_object_key=layout_object_key,
            page_count=len(layout.pages),
            token_count=layout.token_count,
        )

    def extract_pdf_layout(self, job: JobRecord) -> ExtractionResult:
        return self.extract_layout(job)
