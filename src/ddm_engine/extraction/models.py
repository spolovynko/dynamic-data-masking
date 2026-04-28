from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class LayoutToken(BaseModel):
    token_id: str
    page_number: int
    text: str
    bbox: BoundingBox
    block_number: int | None = None
    line_number: int | None = None
    word_number: int | None = None
    source: str = "pdf_text"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PageLayout(BaseModel):
    page_number: int
    width: float
    height: float
    rotation: int
    tokens: list[LayoutToken]


class DocumentLayout(BaseModel):
    job_id: str
    source_file_type: str
    pages: list[PageLayout]

    @property
    def token_count(self) -> int:
        return sum(len(page.tokens) for page in self.pages)
