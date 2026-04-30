from dataclasses import dataclass

from ddm_engine.config import Settings
from ddm_engine.extraction.docx_text import DocxTextExtractor
from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.extraction.ocr import OcrSettings, OcrUnavailableError, PyMuPdfOcrExtractor
from ddm_engine.extraction.pdf_text import PdfTextExtractor
from ddm_engine.extraction.plain_text import PlainTextExtractor
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore

IMAGE_FILE_TYPES = frozenset({"png", "jpg", "jpeg", "tif", "tiff"})


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
        self.artifacts = JsonArtifactStore(object_store)
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
        layout = self._extract_document_layout(job, document_bytes)
        layout_object_key = ArtifactKeys.layout(job.job_id)
        self.artifacts.write_model(layout_object_key, layout)

        return ExtractionResult(
            layout_object_key=layout_object_key,
            page_count=len(layout.pages),
            token_count=layout.token_count,
        )

    def extract_pdf_layout(self, job: JobRecord) -> ExtractionResult:
        return self.extract_layout(job)

    def _extract_document_layout(self, job: JobRecord, document_bytes: bytes) -> DocumentLayout:
        if job.file_type == "pdf":
            return self._extract_pdf_layout(job, document_bytes)
        if job.file_type == "txt":
            return self.plain_text_extractor.extract(job.job_id, document_bytes)
        if job.file_type == "docx":
            return self.docx_text_extractor.extract(job.job_id, document_bytes)
        if job.file_type in IMAGE_FILE_TYPES:
            return self.ocr_extractor.extract(job.job_id, document_bytes, job.file_type)

        raise ValueError(f"Unsupported extraction file type: {job.file_type}")

    def _extract_pdf_layout(self, job: JobRecord, document_bytes: bytes) -> DocumentLayout:
        layout = self.pdf_text_extractor.extract(job.job_id, document_bytes)
        if not self._should_run_pdf_ocr_fallback(layout):
            return layout

        try:
            return self.ocr_extractor.extract(job.job_id, document_bytes, "pdf")
        except OcrUnavailableError:
            return layout

    def _should_run_pdf_ocr_fallback(self, layout: DocumentLayout) -> bool:
        return (
            self.settings.ocr_enabled and layout.token_count < self.settings.ocr_min_native_tokens
        )
