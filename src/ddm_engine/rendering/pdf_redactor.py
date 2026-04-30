from __future__ import annotations

import fitz

from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.observability.metrics import REDACTIONS_APPLIED_TOTAL
from ddm_engine.planning.models import RedactionPlan
from ddm_engine.rendering.layout_pdf import render_layout_to_pdf_bytes
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore

IMAGE_FILE_TYPES = frozenset({"png", "jpg", "jpeg", "tif", "tiff"})


class PDFRedactionError(Exception):
    """Raised when PDF redaction fails."""


class PDFRedactionService:
    def __init__(self, object_store: ObjectStore) -> None:
        self.object_store = object_store
        self.artifacts = JsonArtifactStore(object_store)

    def redact(self, job: JobRecord) -> str:
        plan = self.artifacts.read_model(ArtifactKeys.redaction_plan(job.job_id), RedactionPlan)
        source_bytes, source_filetype = self._source_pdf_bytes(job)
        redacted_object_key = ArtifactKeys.redacted_pdf(job.job_id)

        try:
            document = fitz.open(stream=source_bytes, filetype=source_filetype)
        except Exception as exc:
            raise PDFRedactionError("Failed to open source document for redaction") from exc

        try:
            for region in plan.regions:
                page_index = region.page_number - 1
                if page_index < 0 or page_index >= document.page_count:
                    continue
                page = document[page_index]
                rect = fitz.Rect(
                    region.bbox.x0,
                    region.bbox.y0,
                    region.bbox.x1,
                    region.bbox.y1,
                )
                page.add_redact_annot(rect, fill=(0, 0, 0))
                REDACTIONS_APPLIED_TOTAL.labels(label=region.label).inc()

            for page in document:
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)

            if source_filetype == "pdf":
                redacted_bytes = document.tobytes(garbage=4, deflate=True, clean=True)
            else:
                redacted_bytes = document.convert_to_pdf()
        except Exception as exc:
            raise PDFRedactionError("Failed to apply PDF redactions") from exc
        finally:
            document.close()

        with self.object_store.open_writer(redacted_object_key) as output:
            output.write(redacted_bytes)

        return redacted_object_key

    def _source_pdf_bytes(self, job: JobRecord) -> tuple[bytes, str]:
        if job.file_type == "pdf":
            return self.object_store.read_bytes(job.original_object_key), "pdf"

        if job.file_type in IMAGE_FILE_TYPES:
            image_bytes = self.object_store.read_bytes(job.original_object_key)
            try:
                image_document = fitz.open(stream=image_bytes, filetype=job.file_type)
                try:
                    return image_document.convert_to_pdf(), "pdf"
                finally:
                    image_document.close()
            except Exception as exc:
                raise PDFRedactionError("Failed to convert image to PDF") from exc

        if job.file_type in {"txt", "docx"}:
            layout = self.artifacts.read_model(ArtifactKeys.layout(job.job_id), DocumentLayout)
            return render_layout_to_pdf_bytes(layout), "pdf"

        raise PDFRedactionError(f"Unsupported redaction file type: {job.file_type}")
