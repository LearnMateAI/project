"""
Page text extraction and cleaning.

PDF text arrives with the artefacts of a printed page in it: running heads on every page,
standalone page numbers, curly quotes, bullet glyphs, and words hyphenated across a line
break. All of that ends up in the embedding if it is left alone, and a running head that
repeats on 200 pages is a term the retriever will happily match on.

Newlines are flattened deliberately. Layout in a PDF reflects the column, not the
sentence, so a line break inside a paragraph is noise; sentence boundaries are recovered
downstream by the splitter.
"""

import re
import unicodedata
from typing import Dict, List, Union

KIND_PDF_FALLBACK = "pdf"

# Typographic characters that should not become their own embedding tokens.
_REPLACEMENTS = {
    "“": '"', "”": '"',      # curly double quotes
    "‘": "'", "’": "'",      # curly single quotes
    "–": "-", "—": "-",      # en/em dash
    "•": "-", "●": "-",      # bullets
    "✓": "-", "✔": "-",      # check marks used as bullets
    " ": " ",                     # non-breaking space
    "ﬁ": "fi", "ﬂ": "fl",    # ligatures PyMuPDF leaves intact
}


def extract_pages(file_bytes: bytes, filename: str = None) -> List[Dict]:
    """
    Pull text out of a source file, one entry per page / slide / section.

    Takes bytes rather than a path so it can read straight from GridFS without staging
    the file back onto disk. Kind comes from the filename; PDF is the default when the
    name is missing so older call sites stay valid.
    """
    from .formats import KIND_DOCX, KIND_PPTX, KIND_TEX, detect_kind
    from .extract_office import extract_docx, extract_pptx, extract_tex

    kind = KIND_PDF_FALLBACK
    if filename:
        try:
            kind = detect_kind(filename)
        except ValueError:
            kind = KIND_PDF_FALLBACK

    if kind == KIND_DOCX:
        return extract_docx(file_bytes)
    if kind == KIND_PPTX:
        return extract_pptx(file_bytes)
    if kind == KIND_TEX:
        return extract_tex(file_bytes)

    import fitz  # PyMuPDF

    pages = []
    document = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for index in range(len(document)):
            pages.append({
                "page_index": index,
                "page_number": index + 1,
                "text": document.load_page(index).get_text("text"),
            })
    finally:
        document.close()
    return pages


def clean_text(text: str) -> str:
    """Normalise one page of extracted text."""
    text = unicodedata.normalize("NFKC", text or "")

    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)

    # Standalone page numbers on their own line.
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)

    # Rejoin words split across a line break: "off-\nshore" -> "offshore".
    text = re.sub(r"([A-Za-z])-\s*\n\s*([a-z])", r"\1\2", text)
    text = re.sub(r"([a-zA-Z]+)\s*\n\s*-\s*([a-zA-Z]+)", r"\1\2", text)

    # Leading bullet dashes, which carry no meaning once the layout is gone.
    text = re.sub(r"(?:^|\n)[ \t]*[-*][ \t]+", " ", text)

    # Flatten remaining line breaks, then collapse the whitespace that leaves behind.
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def drop_repeated_lines(pages: List[Dict], min_ratio: float = 0.5) -> List[Dict]:
    """
    Remove running heads and footers.

    A line appearing on more than `min_ratio` of the pages is furniture, not content.
    Detecting it by frequency generalises across documents, where the previous
    hard-coded patterns only matched the two PDFs they were written for.

    Only applied to documents long enough for the ratio to mean something: on a 3-page
    handout a genuine heading can easily appear on two pages.
    """
    if len(pages) < 6:
        return pages

    counts: Dict[str, int] = {}
    for page in pages:
        for line in {ln.strip() for ln in (page["text"] or "").splitlines() if ln.strip()}:
            # Long lines are prose that happens to repeat, not a running head.
            if len(line) <= 90:
                counts[line] = counts.get(line, 0) + 1

    threshold = max(3, int(len(pages) * min_ratio))
    furniture = {line for line, count in counts.items() if count >= threshold}
    if not furniture:
        return pages

    for page in pages:
        kept = [ln for ln in (page["text"] or "").splitlines() if ln.strip() not in furniture]
        page["text"] = "\n".join(kept)
    return pages


def preprocess(file_bytes: bytes, filename: str = None) -> List[Dict]:
    """
    Full page pipeline: extract, strip furniture, clean.

    Returns [{page_index, page_number, page_content}, ...] with empty pages dropped.
    """
    pages = drop_repeated_lines(extract_pages(file_bytes, filename))

    cleaned = []
    for page in pages:
        content = clean_text(page["text"])
        if content:
            cleaned.append({
                "page_index": page["page_index"],
                "page_number": page["page_number"],
                "page_content": content,
            })
    return cleaned


def is_substantive(text: str, min_chars: int) -> bool:
    """
    Reject fragments that are too thin to be worth a vector.

    Measured on alphanumeric characters only, so a line of dot leaders from a contents
    page or a row of section numbers does not pass on its punctuation.
    """
    return len(re.sub(r"[^A-Za-z0-9]", "", text or "")) >= min_chars


# Dot leaders: the run of periods joining an entry to its page number in a table of
# contents or an index. Three or more in one chunk is the signature of a contents page,
# and a single heading followed by an ellipsis never reaches it.
_DOT_LEADER = re.compile(r"(?:\.\s*){3,}")


def looks_like_contents(text: str, min_leaders: int = 3) -> bool:
    """
    Whether a chunk is table-of-contents or index furniture rather than prose.

    These chunks are actively harmful in both directions. In retrieval a contents page is
    a list of every chapter title in the document, so it matches almost any topical query
    and out-scores the article the question is actually about. In generation it is worse:
    asked for questions about "fundamental rights", the model is handed a page of headings
    and page numbers and writes questions about the numbering.

    Detected by dot leaders rather than by page position, because a contents page is not
    always at the front -- the index at the back has the same shape.
    """
    return len(_DOT_LEADER.findall(text or "")) >= min_leaders
