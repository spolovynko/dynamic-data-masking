from typing import Literal

from pydantic import BaseModel, computed_field


class TextPageResponse(BaseModel):
    page_number: int
    text: str

    @computed_field
    @property
    def char_count(self) -> int:
        return len(self.text)


class DocumentTextResponse(BaseModel):
    job_id: str
    source: Literal["extracted", "redacted"]
    pages: list[TextPageResponse]

    @computed_field
    @property
    def page_count(self) -> int:
        return len(self.pages)

    @computed_field
    @property
    def char_count(self) -> int:
        return sum(page.char_count for page in self.pages)
