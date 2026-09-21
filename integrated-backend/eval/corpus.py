"""
The evaluation corpus: open-licensed textbook chapters, each ingested as one "shared notes"
document -- the unit a class uploads.

    python -m eval.corpus fetch
    python -m eval.corpus split
    python -m eval.corpus ingest

Source: *Business Law I Essentials* (Valbrune, De Assis et al.; OpenStax, Rice University,
2019), in its LibreTexts edition -- fetched from there because the OpenStax CDN refuses
scripted downloads. That edition is CC BY-NC-SA 4.0 (its own Detailed Licensing page): fine
for non-commercial research, and the PDFs are never redistributed from this repository.

    https://batch.libretexts.org/print/Finished/biz-10819/Full.pdf

A law textbook on purpose: LearnMate was built for law students, and legal text is where
lexical retrieval should matter most (defined terms, statute names, section numbers).
The PDFs are not committed -- data/ is ignored -- and the manifest records where they came
from, so the corpus can be rebuilt byte-for-byte.

`split` cuts the book at its "CHAPTER OVERVIEW" pages and keeps the chapters listed in
CHAPTERS. `ingest` runs the app's own ingestion pipeline into the eval database, after
fixing BM25's avgdl over the whole corpus first (every sparse vector depends on it, so it
must be known before the first document is indexed, not measured from that document).
"""

import argparse
import re
import sys
from pathlib import Path

from eval.common import CORPUS_DIR, bootstrap, provenance, write_json

SOURCE = {
    "title": "Business Law I Essentials",
    "authors": "Valbrune, De Assis, Cardell, Taylor, Sappleton, Mitchell, Mitchell-Phillips",
    "publisher": "OpenStax, Rice University (2019); LibreTexts edition",
    "license": "CC BY-NC-SA 4.0 (LibreTexts edition)",
    "url": "https://biz.libretexts.org/Bookshelves/Civil_Law/Business_Law_I_Essentials_(OpenStax)",
    "download": "https://batch.libretexts.org/print/Finished/biz-10819/Full.pdf",
}
# Eight of the fourteen chapters: a spread of topics, ~10-17 pages each. Chapter 2 is the
# development document -- thresholds are tuned on it and reported on the other seven.
CHAPTERS = [1, 2, 5, 6, 7, 9, 11, 14]
DEV_CHAPTERS = [2]
DOCS_DIR = CORPUS_DIR / "docs"
MANIFEST = CORPUS_DIR / "corpus.json"


def fetch(target: Path) -> Path:
    """Download the book from the LibreTexts mirror (the OpenStax CDN answers 403)."""
    import hashlib

    import requests

    target.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(SOURCE["download"], timeout=600,
                            headers={"User-Agent": "Mozilla/5.0 (LearnMate evaluation)"})
    response.raise_for_status()
    target.write_bytes(response.content)
    print(f"  {len(response.content) / 1e6:.1f} MB, sha256 "
          f"{hashlib.sha256(response.content).hexdigest()[:16]}... -> {target}")
    return target


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def split(pdf_path: Path) -> list:
    import pymupdf

    book = pymupdf.open(pdf_path)
    starts = []
    for index, page in enumerate(book):
        text = page.get_text()
        if "CHAPTER OVERVIEW" in text[:200]:
            match = re.search(r"CHAPTER OVERVIEW\s*\n\s*(\d+):\s*([^\n]+)", text)
            if match:
                starts.append((index, int(match.group(1)), match.group(2).strip()))
    # Back matter (index, glossary, licensing) ends the last chapter.
    back = next((i for i, page in enumerate(book)
                 if i > starts[-1][0] and re.match(
                     r"\s*(Index|Glossary|Detailed Licensing)\b", page.get_text())),
                book.page_count)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    documents = []
    for position, (overview, number, title) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else back
        if number not in CHAPTERS:
            continue
        # From the page after the overview (a list of section titles, not content).
        first, last = overview + 1, end - 1
        out = pymupdf.open()
        out.insert_pdf(book, from_page=first, to_page=last)
        filename = f"BL1E-ch{number:02d}-{_slug(title)}.pdf"
        out.save(DOCS_DIR / filename, garbage=4, deflate=True)
        documents.append({"chapter": number, "title": title, "filename": filename,
                          "book_pages": [first + 1, last + 1],
                          "split": "dev" if number in DEV_CHAPTERS else "test"})
        print(f"  ch{number:02d} {title!r}: book pages {first + 1}-{last + 1}")
    write_json(MANIFEST, {"source": SOURCE, "documents": documents})
    return documents


def ingest() -> list:
    from learnmate import config
    from learnmate.ingestion import ingest_pdf
    from learnmate.ingestion.chunking import pages_to_documents
    from learnmate.ingestion.clean import preprocess
    from learnmate.retrieval.sparse import ANALYZER_VERSION, mean_doc_length
    from learnmate.storage import retrieval_meta

    import json

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    documents = manifest["documents"]

    # avgdl over the corpus, from exactly the chunks ingestion is about to produce.
    texts = []
    for entry in documents:
        data = (DOCS_DIR / entry["filename"]).read_bytes()
        pages = preprocess(data, filename=entry["filename"])
        texts += [doc.page_content for doc in pages_to_documents(pages, "probe",
                                                                 entry["filename"])]
    avgdl = mean_doc_length(texts)
    retrieval_meta.set_bm25_meta(avgdl, len(texts), ANALYZER_VERSION)
    print(f"[*] avgdl {avgdl:.1f} analyzed terms over {len(texts)} chunks")

    for entry in documents:
        report = ingest_pdf(DOCS_DIR / entry["filename"], filename=entry["filename"],
                            verbose=False)
        entry.update({"doc_id": report["doc_id"], "sha256": report["document"]["sha256"],
                      "n_pages": report["n_pages"], "n_chunks": report["n_chunks"]})
        print(f"  {entry['filename']}: {report['n_pages']} pages, {report['n_chunks']} chunks"
              f"{' (already indexed)' if report['skipped'] else ''}")

    manifest.update({"collection": config.QDRANT_COLLECTION, "database": config.MONGODB_DB,
                     "avgdl": avgdl, "provenance": provenance()})
    write_json(MANIFEST, manifest)
    return documents


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the evaluation corpus.")
    sub = parser.add_subparsers(dest="command", required=True)
    raw = CORPUS_DIR / "raw" / "business_law_i_essentials.pdf"
    sub.add_parser("fetch")
    cut = sub.add_parser("split")
    cut.add_argument("--pdf", type=Path, default=raw)
    sub.add_parser("ingest")
    args = parser.parse_args(argv)

    if args.command == "fetch":
        fetch(raw)
    elif args.command == "split":
        split(args.pdf)
    else:
        bootstrap()
        ingest()
    return 0


if __name__ == "__main__":
    sys.exit(main())
