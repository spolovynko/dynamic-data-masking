import fitz

from ddm_engine.extraction.pdf_text import PdfTextExtractor


def test_pdf_text_extractor_returns_page_tokens_with_coordinates() -> None:
    pdf_bytes = _make_pdf_bytes("Jane Doe\njane@example.com")

    layout = PdfTextExtractor().extract("job-1", pdf_bytes)

    assert layout.job_id == "job-1"
    assert layout.source_file_type == "pdf"
    assert len(layout.pages) == 1
    assert layout.token_count >= 2

    page = layout.pages[0]
    assert page.page_number == 1
    assert page.width > 0
    assert page.height > 0

    token_text = {token.text for token in page.tokens}
    assert {"Jane", "Doe"}.issubset(token_text)
    assert all(token.bbox.x1 > token.bbox.x0 for token in page.tokens)
    assert all(token.bbox.y1 > token.bbox.y0 for token in page.tokens)


def _make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    try:
        return document.tobytes()
    finally:
        document.close()
