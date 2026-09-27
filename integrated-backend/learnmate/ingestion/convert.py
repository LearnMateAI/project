"""Convert supported source documents into PDFs for the canonical pipeline."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List


def convert_to_pdf(file_bytes: bytes, filename: str, kind: str) -> tuple[bytes, str]:
    """Render extracted source text into a PDF and return PDF bytes and filename."""
    if kind == "pdf":
        return file_bytes, filename

    from .extract_office import extract_docx, extract_pptx, extract_tex

    extractors = {
        "docx": extract_docx,
        "pptx": extract_pptx,
        "tex": extract_tex,
    }
    extractor = extractors.get(kind)
    if extractor is None:
        raise ValueError(f"Unsupported source type: {kind}")
    pages = extractor(file_bytes)
    if not pages:
        raise ValueError("This document has no extractable text to convert to PDF.")

    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PDF conversion is unavailable on the server.") from exc

    document = fitz.open()
    try:
        for source_page in pages:
            _add_text_pages(document, source_page.get("text", ""))
        if not len(document):
            raise ValueError("This document has no extractable text to convert to PDF.")
        pdf_bytes = document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()

    pdf_filename = f"{Path(filename).stem or 'document'}.pdf"
    return pdf_bytes, pdf_filename


def _add_text_pages(document, text: str) -> None:
    lines = _wrapped_lines(text)
    if not lines:
        return

    lines_per_page = 48
    for start in range(0, len(lines), lines_per_page):
        page = document.new_page(width=595, height=842)
        y = 54
        for line in lines[start:start + lines_per_page]:
            page.insert_text((54, y), line, fontsize=10, fontname="helv")
            y += 14


def _wrapped_lines(text: str) -> List[str]:
    lines: List[str] = []
    for paragraph in (text or "").replace("\t", "    ").splitlines():
        stripped = paragraph.strip()
        if not stripped:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(stripped, width=92, break_long_words=False,
                                   break_on_hyphens=False))
    return lines
