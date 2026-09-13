"""
Which kind of source file an upload is.

The rest of ingestion is kind-agnostic: everything becomes
`[{page_index, page_number, text}]`, then the same clean / chunk / embed path as a PDF.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

KIND_PDF = "pdf"
KIND_DOCX = "docx"
KIND_PPTX = "pptx"
KIND_TEX = "tex"

SUPPORTED_KINDS = (KIND_PDF, KIND_DOCX, KIND_PPTX, KIND_TEX)

_EXTENSIONS = {
    ".pdf": KIND_PDF,
    ".docx": KIND_DOCX,
    ".pptx": KIND_PPTX,
    ".tex": KIND_TEX,
}

# Legacy Office binaries are a different file format. Say so rather than failing inside
# python-docx / python-pptx with an opaque zip error.
_LEGACY = {
    ".doc": "This is an older Word .doc file. Save it as .docx and upload that.",
    ".ppt": "This is an older PowerPoint .ppt file. Save it as .pptx and upload that.",
}

MEDIA_TYPES = {
    KIND_PDF: "application/pdf",
    KIND_DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    KIND_PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    KIND_TEX: "text/x-tex",
}

UNIT_LABELS = {
    KIND_PDF: "pages",
    KIND_DOCX: "pages",
    KIND_PPTX: "slides",
    KIND_TEX: "sections",
}

# Browsers disagree on Office MIME types; Windows often sends octet-stream for a drag
# from Explorer. Extension is the real gate; this list only rejects an obvious mismatch.
ALLOWED_CONTENT_TYPES = (
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/x-tex",
    "text/x-tex",
    "text/plain",
)


def extension_of(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def detect_kind(filename: str) -> str:
    """
    Kind from the filename. Raises ValueError with a message meant for the uploader.
    """
    ext = extension_of(filename)
    if ext in _LEGACY:
        raise ValueError(_LEGACY[ext])
    kind = _EXTENSIONS.get(ext)
    if not kind:
        raise ValueError(
            "Upload a PDF, Word (.docx), PowerPoint (.pptx), or LaTeX (.tex) file."
        )
    return kind


def media_type_for(kind: str) -> str:
    return MEDIA_TYPES.get(kind) or "application/octet-stream"


def unit_label_for(kind: str) -> str:
    return UNIT_LABELS.get(kind) or "pages"


def looks_like_pdf(data: bytes) -> bool:
    return (data or b"").lstrip()[:4] == b"%PDF"


def looks_like_zip(data: bytes) -> bool:
    return (data or b"")[:2] == b"PK"


def confirm_kind(kind: str, data: bytes) -> None:
    """
    Cheap magic-byte check so a renamed .exe does not reach the Office parsers.
    """
    if not data:
        raise ValueError("This file is empty.")
    if kind == KIND_PDF and not looks_like_pdf(data):
        raise ValueError("This file is not a readable PDF.")
    if kind in (KIND_DOCX, KIND_PPTX) and not looks_like_zip(data):
        raise ValueError(
            f"This file is not a readable .{kind} (Office files are zip packages)."
        )
    if kind == KIND_TEX:
        # UTF-8 / Latin-1 source; reject obvious binaries.
        if b"\x00" in data[:2048]:
            raise ValueError("This does not look like a LaTeX source file.")


def kind_from_record(document: Optional[dict], filename: str = None) -> str:
    """Kind stored on the document, or inferred from its filename."""
    if document:
        stored = document.get("source_kind")
        if stored in SUPPORTED_KINDS:
            return stored
        filename = filename or document.get("filename")
    try:
        return detect_kind(filename or "")
    except ValueError:
        return KIND_PDF
