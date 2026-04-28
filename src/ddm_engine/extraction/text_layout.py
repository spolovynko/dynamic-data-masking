from __future__ import annotations

from dataclasses import dataclass

from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken, PageLayout


@dataclass(frozen=True)
class SyntheticLayoutStyle:
    page_width: float = 612.0
    page_height: float = 792.0
    margin_x: float = 72.0
    margin_y: float = 72.0
    line_height: float = 16.0
    char_width: float = 6.0


class TextLayoutBuilder:
    def __init__(self, style: SyntheticLayoutStyle | None = None) -> None:
        self.style = style or SyntheticLayoutStyle()

    def build(self, job_id: str, source_file_type: str, text: str) -> DocumentLayout:
        pages: list[PageLayout] = []
        current_tokens: list[LayoutToken] = []
        page_number = 1
        y = self.style.margin_y
        token_index = 1

        for line_number, line in enumerate(text.splitlines() or [text], start=1):
            if y + self.style.line_height > self.style.page_height - self.style.margin_y:
                pages.append(self._page(page_number, current_tokens))
                page_number += 1
                current_tokens = []
                y = self.style.margin_y
                token_index = 1

            x = self.style.margin_x
            for word_number, word in enumerate(line.split(), start=1):
                width = max(self.style.char_width, len(word) * self.style.char_width)
                current_tokens.append(
                    LayoutToken(
                        token_id=f"p{page_number}-t{token_index}",
                        page_number=page_number,
                        text=word,
                        bbox=BoundingBox(
                            x0=x,
                            y0=y,
                            x1=min(x + width, self.style.page_width - self.style.margin_x),
                            y1=y + self.style.line_height,
                        ),
                        block_number=0,
                        line_number=line_number,
                        word_number=word_number,
                        source="synthetic_text",
                        confidence=1.0,
                    )
                )
                token_index += 1
                x += width + self.style.char_width
            y += self.style.line_height

        pages.append(self._page(page_number, current_tokens))
        return DocumentLayout(job_id=job_id, source_file_type=source_file_type, pages=pages)

    def _page(self, page_number: int, tokens: list[LayoutToken]) -> PageLayout:
        return PageLayout(
            page_number=page_number,
            width=self.style.page_width,
            height=self.style.page_height,
            rotation=0,
            tokens=tokens,
        )
