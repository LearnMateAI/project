"""
Super Chunker — PyMuPDF-based PDF chunking for RAG ingestion.

Automatically detects presentation/slide PDFs vs long-form documents and applies
the appropriate strategy:

  * Slides  → one chunk per slide (page), preserving slide title + body.
  * Documents → semantic chunks grouped under detected heading/subheading hierarchy
                using font size, bold/highlight, and numbering patterns
                (roman numerals, decimal outlines, chapter/section labels, etc.).

Usage:
    from ingestion.super_chunker import SuperChunker

    chunker = SuperChunker(max_chunk_size=1200)
    chunks = chunker.chunk_pdf("path/to/file.pdf", doc_metadata={"source": "notes.pdf"})
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from ingestion.document_models import Chunk

# ---------------------------------------------------------------------------
# PyMuPDF span flags (https://pymupdf.readthedocs.io/en/latest/textpage.html)
# ---------------------------------------------------------------------------
_SPAN_BOLD = 16
_SPAN_ITALIC = 2


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class PDFKind(str, Enum):
    SLIDE = "slide"
    DOCUMENT = "document"


@dataclass
class TextSpan:
    text: str
    font: str
    size: float
    flags: int
    color: int  # sRGB int, 0 = black


@dataclass
class TextLine:
    """One visual line on a PDF page with typographic signals."""

    text: str
    page_number: int
    font_size: float
    is_bold: bool
    is_italic: bool
    is_highlighted: bool  # non-black or light-background emphasis
    bbox: Tuple[float, float, float, float]
    spans: List[TextSpan] = field(default_factory=list)

    @property
    def y0(self) -> float:
        return self.bbox[1]


@dataclass
class Heading:
    level: int
    title: str
    page_number: int
    line_index: int
    confidence: float
    signals: List[str] = field(default_factory=list)


@dataclass
class Section:
    """A heading and all body content until the next heading of equal/higher level."""

    heading: Optional[Heading]
    lines: List[TextLine] = field(default_factory=list)

    def full_heading_path(self) -> List[str]:
        return []

    def body_text(self) -> str:
        return _lines_to_text(self.lines)


# ---------------------------------------------------------------------------
# Heading pattern library
# ---------------------------------------------------------------------------

# Level → list of compiled regexes (match at line start)
_HEADING_PATTERNS: Dict[int, List[re.Pattern]] = {
    1: [
        re.compile(r"^(?:CHAPTER|Chapter|PART|Part|UNIT|Unit|MODULE|Module)\s*[-–.:]?\s*(?:[IVXLCDM]+|\d+)\b", re.I),
        re.compile(r"^(?:[IVXLCDM]{1,8})\.\s+\S", re.I),  # I. Introduction
        re.compile(r"^(?:SECTION|Section)\s+\d+\b", re.I),
        re.compile(r"^\d+\.\s+[A-Z][\w\s,&'-]{2,}$"),  # 1. Major Topic
    ],
    2: [
        re.compile(r"^\d+\.\d+\.?\s+\S"),  # 1.1 Subtopic
        re.compile(r"^(?:[A-Z])\.\s+\S"),  # A. Item
        re.compile(r"^(?:Article|ARTICLE|Art\.?)\s+\d+\b", re.I),
        re.compile(r"^(?:§|Section)\s+\d+\.\d+\b"),
    ],
    3: [
        re.compile(r"^\d+\.\d+\.\d+\.?\s+\S"),  # 1.1.1 Detail
        re.compile(r"^\([a-z]\)\s+\S"),  # (a) sub-item
        re.compile(r"^\([ivxlc]+\)\s+\S", re.I),  # (i) roman sub-item
        re.compile(r"^(?:[a-z])\.\s+\S"),  # a. minor point
    ],
    4: [
        re.compile(r"^\d+\.\d+\.\d+\.\d+\.?\s+\S"),
        re.compile(r"^\([A-Z]\)\s+\S"),
        re.compile(r"^\([0-9]+\)\s+\S"),
    ],
}

_ROMAN_ONLY = re.compile(r"^[IVXLCDM]{1,8}\.?$", re.I)
_ALL_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9\s,&'\-/]{4,}$")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _span_is_bold(flags: int) -> bool:
    return bool(flags & _SPAN_BOLD)


def _span_is_italic(flags: int) -> bool:
    return bool(flags & _SPAN_ITALIC)


def _span_is_highlighted(color: int) -> bool:
    """Treat non-black / saturated colors as emphasis (common in slides & notes)."""
    if color == 0:
        return False
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    # Highlight-like: strong single channel or very light fill colors
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    return max_c > 40 and (max_c - min_c > 60 or (r > 200 and g > 200))


def extract_lines(doc: fitz.Document) -> List[TextLine]:
    """Extract reading-ordered lines with font metadata from every page."""
    all_lines: List[TextLine] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_number = page_idx + 1
        raw_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])

        page_lines: List[TextLine] = []
        for block in raw_blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans_raw = line.get("spans", [])
                if not spans_raw:
                    continue

                parts: List[str] = []
                span_objs: List[TextSpan] = []
                sizes: List[float] = []
                bold_votes = 0
                italic_votes = 0
                highlight_votes = 0

                for s in spans_raw:
                    t = s.get("text", "")
                    if not t:
                        continue
                    parts.append(t)
                    flags = int(s.get("flags", 0))
                    color = int(s.get("color", 0))
                    size = float(s.get("size", 0))
                    span_objs.append(
                        TextSpan(
                            text=t,
                            font=s.get("font", ""),
                            size=size,
                            flags=flags,
                            color=color,
                        )
                    )
                    sizes.append(size)
                    if _span_is_bold(flags):
                        bold_votes += len(t)
                    if _span_is_italic(flags):
                        italic_votes += len(t)
                    if _span_is_highlighted(color):
                        highlight_votes += len(t)

                text = "".join(parts).strip()
                if not text:
                    continue

                char_count = max(len(text), 1)
                page_lines.append(
                    TextLine(
                        text=text,
                        page_number=page_number,
                        font_size=statistics.mean(sizes) if sizes else 0.0,
                        is_bold=bold_votes > char_count * 0.5,
                        is_italic=italic_votes > char_count * 0.5,
                        is_highlighted=highlight_votes > char_count * 0.3,
                        bbox=tuple(line["bbox"]),
                        spans=span_objs,
                    )
                )

        # Sort top-to-bottom, then left-to-right (reading order)
        page_lines.sort(key=lambda ln: (round(ln.y0, 1), ln.bbox[0]))
        all_lines.extend(page_lines)

    return all_lines


def _lines_to_text(lines: List[TextLine]) -> str:
    if not lines:
        return ""
    chunks: List[str] = []
    buf: List[str] = []
    prev: Optional[TextLine] = None

    for line in lines:
        if prev is None:
            buf = [line.text]
        else:
            vertical_gap = line.y0 - prev.bbox[3]
            same_page = line.page_number == prev.page_number
            # Large vertical gap → paragraph break
            if same_page and vertical_gap > prev.font_size * 1.6:
                chunks.append(" ".join(buf))
                buf = [line.text]
            elif not same_page:
                chunks.append(" ".join(buf))
                buf = [line.text]
            else:
                buf.append(line.text)
        prev = line

    if buf:
        chunks.append(" ".join(buf))

    return "\n\n".join(c.strip() for c in chunks if c.strip())


# ---------------------------------------------------------------------------
# PDF type detection
# ---------------------------------------------------------------------------


def detect_pdf_kind(doc: fitz.Document, lines: List[TextLine]) -> PDFKind:
    """
    Heuristic slide vs document classifier.

    Slides tend to have: landscape pages, few words/page, large title fonts,
    repeated sparse layouts.
    """
    if len(doc) == 0:
        return PDFKind.DOCUMENT

    sample_pages = min(len(doc), 12)
    landscape = 0
    word_counts: List[int] = []
    title_ratios: List[float] = []

    for i in range(sample_pages):
        page = doc[i]
        w, h = page.rect.width, page.rect.height
        if w > h * 1.15:
            landscape += 1

        page_lines = [ln for ln in lines if ln.page_number == i + 1]
        text = " ".join(ln.text for ln in page_lines)
        words = len(text.split())
        word_counts.append(words)

        if page_lines:
            sizes = [ln.font_size for ln in page_lines]
            med = statistics.median(sizes)
            big = sum(1 for s in sizes if s >= med * 1.25)
            title_ratios.append(big / max(len(sizes), 1))

    avg_words = statistics.mean(word_counts) if word_counts else 999
    avg_title_ratio = statistics.mean(title_ratios) if title_ratios else 0
    landscape_ratio = landscape / sample_pages

    slide_score = 0
    if avg_words < 90:
        slide_score += 2
    elif avg_words < 140:
        slide_score += 1
    if landscape_ratio >= 0.6:
        slide_score += 2
    elif landscape_ratio >= 0.35:
        slide_score += 1
    if avg_title_ratio >= 0.15:
        slide_score += 1

    return PDFKind.SLIDE if slide_score >= 3 else PDFKind.DOCUMENT


# ---------------------------------------------------------------------------
# Heading detection (documents)
# ---------------------------------------------------------------------------


def _body_font_size(lines: List[TextLine]) -> float:
    sizes = [ln.font_size for ln in lines if ln.font_size > 0]
    if not sizes:
        return 11.0
    return float(statistics.median(sizes))


def _pattern_heading_level(text: str) -> Tuple[Optional[int], Optional[str]]:
    stripped = text.strip()
    for level, patterns in _HEADING_PATTERNS.items():
        for pat in patterns:
            if pat.match(stripped):
                return level, "pattern"
    if _ROMAN_ONLY.match(stripped):
        return 1, "roman_only"
    return None, None


def _score_heading(line: TextLine, body_size: float) -> Tuple[float, int, List[str]]:
    """Return (confidence 0-1, level, signals)."""
    text = line.text.strip()
    if len(text) < 2 or len(text) > 220:
        return 0.0, 0, []

    signals: List[str] = []
    score = 0.0
    level = 3

    pat_level, pat_name = _pattern_heading_level(text)
    if pat_level is not None:
        score += 0.45
        level = pat_level
        signals.append(pat_name or "pattern")

    if body_size > 0 and line.font_size >= body_size * 1.15:
        ratio = line.font_size / body_size
        score += min(0.35, 0.12 * (ratio - 1.0) / 0.3)
        signals.append("font_size")
        if ratio >= 1.5:
            level = min(level, 1)
        elif ratio >= 1.25:
            level = min(level, 2)

    if line.is_bold and len(text) < 120:
        score += 0.2
        signals.append("bold")

    if line.is_highlighted and len(text) < 120:
        score += 0.12
        signals.append("highlight")

    if _ALL_CAPS_HEADING.match(text) and len(text.split()) <= 12:
        score += 0.18
        signals.append("all_caps")
        level = min(level, 2)

    # Short bold/colored lines that look like titles (not full sentences)
    word_count = len(text.split())
    if word_count <= 10 and not text.endswith((".", "?", "!")):
        if line.is_bold or line.font_size >= body_size * 1.1:
            score += 0.08
            signals.append("short_title")

    # Penalize lines that look like body text
    if word_count > 18 and not pat_level:
        score -= 0.25
    if text.endswith((".", ";")) and word_count > 8 and not line.is_bold:
        score -= 0.2

    score = max(0.0, min(1.0, score))
    if score < 0.42:
        return 0.0, 0, []
    return score, level, signals


def detect_headings(lines: List[TextLine]) -> List[Heading]:
    body_size = _body_font_size(lines)
    headings: List[Heading] = []

    for idx, line in enumerate(lines):
        conf, level, signals = _score_heading(line, body_size)
        if conf <= 0:
            continue
        headings.append(
            Heading(
                level=level,
                title=line.text.strip(),
                page_number=line.page_number,
                line_index=idx,
                confidence=conf,
                signals=signals,
            )
        )
    return headings


def _build_sections(lines: List[TextLine], headings: List[Heading]) -> List[Section]:
    if not headings:
        return [Section(heading=None, lines=lines)]

    heading_indices = {h.line_index for h in headings}
    sections: List[Section] = []
    current_heading: Optional[Heading] = None
    current_lines: List[TextLine] = []

    for idx, line in enumerate(lines):
        if idx in heading_indices:
            if current_lines or current_heading is not None:
                sections.append(Section(heading=current_heading, lines=current_lines))
            current_heading = next(h for h in headings if h.line_index == idx)
            current_lines = []
        else:
            current_lines.append(line)

    sections.append(Section(heading=current_heading, lines=current_lines))
    return sections


def _heading_breadcrumb(sections: List[Section], section_idx: int) -> List[str]:
    """Build hierarchical path e.g. ['Chapter 1', '1.1 Definitions']."""
    if section_idx >= len(sections):
        return []

    target = sections[section_idx].heading
    if target is None:
        return []

    path: List[str] = []
    active: Dict[int, str] = {}

    for i in range(section_idx + 1):
        h = sections[i].heading
        if h is None:
            continue
        # Drop deeper levels when we encounter a higher/equal heading
        active = {lvl: title for lvl, title in active.items() if lvl < h.level}
        active[h.level] = h.title
        if i == section_idx:
            path = [active[lvl] for lvl in sorted(active.keys())]

    return path


# ---------------------------------------------------------------------------
# Chunking strategies
# ---------------------------------------------------------------------------


def chunk_slides(
    lines: List[TextLine],
    doc_metadata: Dict[str, Any],
    min_chars: int = 15,
) -> List[Chunk]:
    """One chunk per slide/page."""
    pages: Dict[int, List[TextLine]] = {}
    for ln in lines:
        pages.setdefault(ln.page_number, []).append(ln)

    chunks: List[Chunk] = []
    for page_num in sorted(pages.keys()):
        page_lines = pages[page_num]
        text = _lines_to_text(page_lines)
        if len(text.strip()) < min_chars:
            continue

        # Try to split slide title (largest / first bold line) from body
        title = ""
        body_lines = page_lines
        if page_lines:
            body_size = _body_font_size(page_lines)
            candidates = [
                ln for ln in page_lines[:4]
                if ln.font_size >= body_size * 1.1 or ln.is_bold
            ]
            if candidates:
                title_line = max(candidates, key=lambda ln: ln.font_size)
                title = title_line.text.strip()
                body_lines = [ln for ln in page_lines if ln is not title_line]

        body = _lines_to_text(body_lines)
        content = f"# {title}\n\n{body}".strip() if title and body else (title or body or text)

        meta = doc_metadata.copy()
        meta.update(
            {
                "page_number": page_num,
                "chunk_type": "slide",
                "slide_title": title or None,
            }
        )
        chunks.append(Chunk(content=content, metadata=meta))

    return chunks


def _split_text_preserving_paragraphs(text: str, max_size: int) -> List[str]:
    text = text.strip()
    if len(text) <= max_size:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    parts: List[str] = []
    buf = ""

    for para in paragraphs:
        if len(para) > max_size:
            if buf:
                parts.append(buf.strip())
                buf = ""
            # Hard split long paragraphs at sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                if buf and len(buf) + len(sent) + 1 > max_size:
                    parts.append(buf.strip())
                    buf = sent
                else:
                    buf = f"{buf} {sent}".strip() if buf else sent
            continue

        if buf and len(buf) + len(para) + 2 > max_size:
            parts.append(buf.strip())
            buf = para
        else:
            buf = f"{buf}\n\n{para}".strip() if buf else para

    if buf:
        parts.append(buf.strip())
    return parts


def chunk_document_semantic(
    lines: List[TextLine],
    doc_metadata: Dict[str, Any],
    max_chunk_size: int = 1200,
    min_chunk_size: int = 80,
    merge_siblings_under: int = 200,
) -> List[Chunk]:
    """
    Chunk by heading/subheading hierarchy. Each chunk keeps its breadcrumb path
    so retrieval preserves section context.
    """
    headings = detect_headings(lines)
    sections = _build_sections(lines, headings)

    raw_chunks: List[Tuple[str, str, Dict[str, Any]]] = []

    for sec_idx, section in enumerate(sections):
        body = section.body_text()
        if not body.strip() and section.heading is None:
            continue

        breadcrumb = _heading_breadcrumb(sections, sec_idx)
        heading_title = section.heading.title if section.heading else ""
        path_prefix = " > ".join(breadcrumb) if breadcrumb else heading_title

        if path_prefix and body:
            content = f"## {path_prefix}\n\n{body}"
        elif path_prefix:
            content = f"## {path_prefix}"
        else:
            content = body

        meta_extra = {
            "chunk_type": "semantic_section",
            "heading": heading_title or None,
            "heading_level": section.heading.level if section.heading else None,
            "heading_path": breadcrumb,
            "page_number": section.heading.page_number if section.heading else (
                section.lines[0].page_number if section.lines else 1
            ),
            "heading_signals": section.heading.signals if section.heading else [],
        }
        raw_chunks.append((content, body, meta_extra))

    # Merge tiny adjacent sections that share the same parent path
    merged: List[Tuple[str, str, Dict[str, Any]]] = []
    i = 0
    while i < len(raw_chunks):
        content, body, meta = raw_chunks[i]
        if len(body) < merge_siblings_under and i + 1 < len(raw_chunks):
            next_content, next_body, next_meta = raw_chunks[i + 1]
            if meta.get("heading_level") == next_meta.get("heading_level"):
                combined_body = f"{body}\n\n{next_body}".strip()
                combined_path = meta.get("heading_path", []) + next_meta.get("heading_path", [])[-1:]
                combined_meta = meta.copy()
                combined_meta["heading_path"] = combined_path
                combined_content = f"## {' > '.join(combined_path)}\n\n{combined_body}" if combined_path else combined_body
                merged.append((combined_content, combined_body, combined_meta))
                i += 2
                continue
        merged.append((content, body, meta))
        i += 1

    # Split oversized sections, emit Chunk objects
    chunks: List[Chunk] = []
    for content, body, meta_extra in merged:
        if len(content) <= max_chunk_size:
            if len(body.strip()) < min_chunk_size and not meta_extra.get("heading"):
                continue
            meta = doc_metadata.copy()
            meta.update(meta_extra)
            chunks.append(Chunk(content=content.strip(), metadata=meta))
            continue

        parts = _split_text_preserving_paragraphs(content, max_chunk_size)
        path = meta_extra.get("heading_path") or []
        for part_idx, part in enumerate(parts):
            meta = doc_metadata.copy()
            meta.update(meta_extra)
            meta["chunk_part"] = part_idx + 1
            meta["chunk_parts_total"] = len(parts)
            if path:
                meta["heading_path"] = path
            chunks.append(Chunk(content=part.strip(), metadata=meta))

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class SuperChunker:
    """
    Main entry point: load a PDF with PyMuPDF, detect its kind, and chunk it.
    """

    def __init__(
        self,
        max_chunk_size: int = 1200,
        min_chunk_size: int = 80,
        force_kind: Optional[PDFKind] = None,
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.force_kind = force_kind

    def chunk_pdf(
        self,
        pdf_path: str | Path,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        base_meta: Dict[str, Any] = {"source": pdf_path.name}
        if doc_metadata:
            base_meta.update(doc_metadata)

        with fitz.open(pdf_path) as doc:
            lines = extract_lines(doc)
            kind = self.force_kind or detect_pdf_kind(doc, lines)

            if kind == PDFKind.SLIDE:
                chunks = chunk_slides(lines, base_meta)
            else:
                chunks = chunk_document_semantic(
                    lines,
                    base_meta,
                    max_chunk_size=self.max_chunk_size,
                    min_chunk_size=self.min_chunk_size,
                )

            for c in chunks:
                c.metadata["pdf_kind"] = kind.value

            return chunks

    def chunk_pdf_with_debug(
        self,
        pdf_path: str | Path,
        doc_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Chunk], Dict[str, Any]]:
        """Same as chunk_pdf but also returns detection/debug info."""
        pdf_path = Path(pdf_path)
        base_meta: Dict[str, Any] = {"source": pdf_path.name}
        if doc_metadata:
            base_meta.update(doc_metadata)

        with fitz.open(pdf_path) as doc:
            lines = extract_lines(doc)
            kind = self.force_kind or detect_pdf_kind(doc, lines)
            headings = detect_headings(lines) if kind == PDFKind.DOCUMENT else []

            if kind == PDFKind.SLIDE:
                chunks = chunk_slides(lines, base_meta)
            else:
                chunks = chunk_document_semantic(
                    lines,
                    base_meta,
                    max_chunk_size=self.max_chunk_size,
                    min_chunk_size=self.min_chunk_size,
                )

            for c in chunks:
                c.metadata["pdf_kind"] = kind.value

            debug = {
                "pdf_kind": kind.value,
                "page_count": len(doc),
                "line_count": len(lines),
                "headings_detected": [
                    {
                        "level": h.level,
                        "title": h.title,
                        "page": h.page_number,
                        "confidence": round(h.confidence, 2),
                        "signals": h.signals,
                    }
                    for h in headings
                ],
                "chunk_count": len(chunks),
            }
            return chunks, debug


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Super Chunker — PyMuPDF PDF chunking")
    parser.add_argument("pdf", type=str, help="Path to PDF file")
    parser.add_argument("--force", choices=["slide", "document"], default=None)
    parser.add_argument("--max-size", type=int, default=1200)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    force = PDFKind(args.force) if args.force else None
    chunker = SuperChunker(max_chunk_size=args.max_size, force_kind=force)

    if args.debug:
        chunks, debug = chunker.chunk_pdf_with_debug(args.pdf)
        print(json.dumps(debug, indent=2))
        print("\n--- Sample chunks ---")
        for i, ch in enumerate(chunks[:5]):
            print(f"\n[Chunk {i + 1}] meta={ch.metadata}")
            print(ch.content[:400] + ("..." if len(ch.content) > 400 else ""))
    else:
        chunks = chunker.chunk_pdf(args.pdf)
        print(f"Produced {len(chunks)} chunks.")
        for i, ch in enumerate(chunks[:3]):
            print(f"\n--- Chunk {i + 1} ---")
            print(ch.content[:500])
