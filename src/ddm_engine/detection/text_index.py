import re
from dataclasses import dataclass

from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken


@dataclass(frozen=True)
class IndexedToken:
    token: LayoutToken
    start: int
    end: int


@dataclass(frozen=True)
class PageTextIndex:
    page_number: int
    text: str
    tokens: list[IndexedToken]

    def tokens_for_span(self, start: int, end: int) -> list[LayoutToken]:
        return [
            indexed.token
            for indexed in self.tokens
            if indexed.start < end and indexed.end > start
        ]

    def find_text_span(self, needle: str) -> tuple[int, int] | None:
        direct_start = self.text.find(needle)
        if direct_start >= 0:
            return direct_start, direct_start + len(needle)

        pattern = re.escape(needle.strip())
        pattern = re.sub(r"\\\s+", r"\\s+", pattern)
        match = re.search(pattern, self.text, flags=re.IGNORECASE)
        if match is not None:
            return match.start(), match.end()

        normalized_needle = _normalize_for_lookup(needle)
        if not normalized_needle:
            return None
        normalized_text, position_map = _normalized_text_with_positions(self.text)
        normalized_start = normalized_text.find(normalized_needle)
        if normalized_start < 0:
            return None
        normalized_end = normalized_start + len(normalized_needle)
        return position_map[normalized_start], position_map[normalized_end - 1] + 1


def build_page_text_indexes(layout: DocumentLayout) -> list[PageTextIndex]:
    indexes: list[PageTextIndex] = []
    for page in layout.pages:
        parts: list[str] = []
        tokens: list[IndexedToken] = []
        cursor = 0

        for token in page.tokens:
            if parts:
                parts.append(" ")
                cursor += 1
            start = cursor
            parts.append(token.text)
            cursor += len(token.text)
            tokens.append(IndexedToken(token=token, start=start, end=cursor))

        indexes.append(
            PageTextIndex(
                page_number=page.page_number,
                text="".join(parts),
                tokens=tokens,
            )
        )
    return indexes


def boxes_for_tokens(tokens: list[LayoutToken]) -> list[BoundingBox]:
    return [token.bbox for token in tokens]


def _normalize_for_lookup(text: str) -> str:
    return "".join(character.casefold() for character in text if character.isalnum())


def _normalized_text_with_positions(text: str) -> tuple[str, list[int]]:
    normalized_parts: list[str] = []
    positions: list[int] = []
    for position, character in enumerate(text):
        if character.isalnum():
            normalized_parts.append(character.casefold())
            positions.append(position)
    return "".join(normalized_parts), positions
