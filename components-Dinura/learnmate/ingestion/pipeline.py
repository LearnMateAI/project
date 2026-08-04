"""
PDF ingestion: store the file, chunk its text, embed the chunks into MongoDB.

    store_pdf (GridFS)  ->  extract + clean pages  ->  split  ->  embed  ->  chunks

Chunking is sub-page. One vector per page averages every provision on that page together,
so the specific article a question asks about is diluted by everything printed beside it,
and a keyword-dense contents page out-scores the article text because a list of chapter
titles matches almost any topical query.

The separators below are ordered so a split falls at the largest boundary that fits:
sentence ends first, then the numbered-clause markers that structure legal and academic
prose -- "(2)", "(iii)" -- then clause punctuation, and only then whitespace.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .. import config
from ..storage import pdf_store
from ..storage.vectors import get_vector_store
from .clean import is_substantive, looks_like_contents, preprocess

_SEPARATORS = [
    ". ",   # sentence end
    "; ",   # clause end, very common in legal prose
    ": ",
    "? ",
    "! ",
    ") ",   # tail of a numbered clause marker
    ", ",
    " ",
    "",
]


def build_splitter(chunk_size: int = None, chunk_overlap: int = None
                   ) -> RecursiveCharacterTextSplitter:
    """
    The text splitter used for every document.

    The overlap keeps a provision that straddles a chunk boundary retrievable from either
    side, which matters most for exactly the long sentences legal text is made of.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or config.CHUNK_SIZE,
        chunk_overlap=chunk_overlap or config.CHUNK_OVERLAP,
        separators=_SEPARATORS,
        keep_separator=True,
        length_function=len,
    )


def pages_to_documents(pages: List[Dict], doc_id, filename: str,
                       splitter: RecursiveCharacterTextSplitter = None) -> List[Document]:
    """
    Split cleaned pages into LangChain Documents carrying their provenance.

    `chunk_index` is per page and, with doc_id and page_number, gives every chunk a stable
    identity -- that triple is the unique key the vector store upserts on, so re-ingesting
    a document overwrites its chunks instead of duplicating them.
    """
    splitter = splitter or build_splitter()

    documents = []
    for page in pages:
        content = page.get("page_content", "")
        if not content:
            continue

        index = 0
        # Checked here rather than per chunk: the splitter treats ". " as a boundary, so
        # by the time a contents page has been split its dot leaders have been broken
        # apart and the chunks no longer look like what they are. The page still does.
        if looks_like_contents(content, min_leaders=4):
            continue
        for piece in splitter.split_text(content):
            piece = piece.strip()
            if not is_substantive(piece, config.MIN_CHUNK_CHARS):
                continue
            if looks_like_contents(piece):
                continue
            documents.append(Document(
                page_content=piece,
                metadata={
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_number": page["page_number"],
                    "chunk_index": index,
                    "source": filename,
                },
            ))
            index += 1
    return documents


def ingest_pdf(source: Union[str, Path, bytes], filename: str = None,
               force: bool = False, verbose: bool = True) -> Dict:
    """
    Store and index one PDF.

    `source` is a path or raw bytes, so this serves a CLI argument and an HTTP upload
    equally. Returns a report with the document record and what was indexed.

    A PDF already ingested is skipped unless `force` is set: identity is the hash of the
    file's bytes, so re-uploading the same document under a new name costs nothing rather
    than re-embedding a few thousand chunks.
    """
    def log(message):
        if verbose:
            print(message)

    started = time.time()
    document = pdf_store.store_pdf(source, filename=filename)
    doc_id = document["_id"]

    store = get_vector_store()
    already_indexed = store.count(doc_id)

    if document.get("existing") and already_indexed and not force:
        log(f"[=] Already ingested: {document['filename']} "
            f"({already_indexed} chunks). Use --force to re-index.")
        return {
            "document": document,
            "doc_id": str(doc_id),
            "skipped": True,
            "n_pages": document.get("n_pages"),
            "n_chunks": already_indexed,
            "elapsed_s": round(time.time() - started, 2),
        }

    log(f"[*] Stored {document['filename']} "
        f"({document['size_bytes'] / 1_048_576:.1f} MB) as {doc_id}")

    pdf_bytes = pdf_store.get_pdf_bytes(doc_id)
    pages = preprocess(pdf_bytes)
    if not pages:
        raise ValueError(
            f"No extractable text in {document['filename']}. If it is a scanned PDF it "
            "needs OCR before it can be indexed."
        )
    log(f"[*] Extracted {len(pages)} pages with text")

    documents = pages_to_documents(pages, doc_id, document["filename"])
    if not documents:
        raise ValueError(f"No substantive chunks produced from {document['filename']}.")
    log(f"[*] {len(pages)} pages -> {len(documents)} chunks")

    if force and already_indexed:
        # Clear both collections before rewriting. Upserting alone would leave behind any
        # page or chunk the new run no longer produces -- which is exactly what happens
        # when a filter is tightened and pages start being dropped.
        store.delete(doc_id=doc_id)
        pdf_store.delete_pages(doc_id)

    # Keep the readable page text too; chunks are shaped for retrieval, not for reading.
    indexed_pages = {doc.metadata["page_number"] for doc in documents}
    pdf_store.store_pages(doc_id, [p for p in pages if p["page_number"] in indexed_pages])

    log(f"[*] Embedding {len(documents)} chunks into {store.describe_backend()}...")
    store.add_documents(documents)
    pdf_store.mark_ingested(doc_id, len(pages), len(documents))

    elapsed = round(time.time() - started, 2)
    log(f"[+] Ingested {document['filename']} in {elapsed}s")

    return {
        "document": pdf_store.get_document(doc_id),
        "doc_id": str(doc_id),
        "skipped": False,
        "n_pages": len(pages),
        "n_chunks": len(documents),
        "elapsed_s": elapsed,
    }


def build_source_text(doc_id, topic: str = None, pages: Optional[List[int]] = None,
                      max_chars: int = None) -> str:
    """
    Assemble the passage a resource is generated from.

    A whole PDF does not fit in a 4k context window, so the interesting question is which
    part of it to use. Three ways, in order of how specific the caller was:

        topic given  -> the pages whose text best matches it. This is what makes
                        "5 MCQs about directors' duties" work on a 200-page book.
        pages given  -> exactly those pages
        neither      -> the opening of the document, up to the budget

    The unit is always a whole page, never the retrieved chunks themselves. Chunks are
    sized and overlapped for retrieval: joining them repeats ~150 characters at every
    boundary and starts the passage mid-sentence, and a generator handed that writes
    questions about the fragments. Retrieval picks *which* pages; the pages supply the
    prose. They are then emitted in reading order, because relevance order reads as
    non-sequitur.
    """
    max_chars = max_chars or config.MAX_SOURCE_CHARS

    if topic:
        # Rank pages by their best-matching chunk, then read those pages whole.
        hits = get_vector_store().similarity_search_with_score(topic, k=12, doc_id=doc_id)
        ranked, seen = [], set()
        for document, _ in hits:
            number = document.metadata.get("page_number")
            if number is not None and number not in seen:
                seen.add(number)
                ranked.append(number)
        selected = ranked
    else:
        selected = pages

    records = pdf_store.get_pages(doc_id, selected)

    if not records:
        # Nothing stored by store_pages: either the document predates it or only chunks
        # exist. Fall back to the chunks so an older corpus still generates.
        documents = get_vector_store().chunks_for(doc_id, pages=selected)
        records = [{"page_number": d.metadata.get("page_number"), "text": d.page_content}
                   for d in documents]

    if not records:
        raise ValueError(
            f"No indexed text for document {doc_id}"
            + (f" matching {topic!r}" if topic else "")
            + ". Ingest the PDF first."
        )

    if topic:
        # get_pages returns reading order; keep only the budget's worth of the most
        # relevant pages, then restore reading order among those.
        rank = {number: position for position, number in enumerate(selected)}
        records.sort(key=lambda r: rank.get(r["page_number"], len(rank)))

        kept, total = [], 0
        for record in records:
            if total and total + len(record["text"]) > max_chars:
                continue
            kept.append(record)
            total += len(record["text"]) + 2
        records = sorted(kept, key=lambda r: r["page_number"])

    parts, total = [], 0
    for record in records:
        text = (record.get("text") or "").strip()
        if not text:
            continue
        if total + len(text) > max_chars:
            remaining = max_chars - total
            # Only take a partial page if enough of it fits to be worth reading.
            if remaining > 300:
                parts.append(text[:remaining])
            break
        parts.append(text)
        total += len(text) + 2

    return "\n\n".join(parts).strip()
