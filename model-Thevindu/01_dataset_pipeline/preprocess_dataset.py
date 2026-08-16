"""
Stage 1 CLI — parse / clean / chunk legal source files.

Usage:
  python preprocess_dataset.py --input_dir data/raw_pdfs --output_dir processed
  python preprocess_dataset.py --input_dir raw_pdfs/ --output_dir processed/
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import traceback
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Allow importing sibling scripts/
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from common import (  # noqa: E402
    compile_patterns,
    load_config,
    slugify,
    utc_now_iso,
    write_json,
    write_jsonl,
)
from stage1_parse_chunk import (  # noqa: E402
    chunk_units,
    detect_structure,
    extract_pages,
    strip_headers_footers,
)

def looks_like_toc(text: str) -> bool:
    """True for table-of-contents / index blocks rather than substantive text.

    A TOC chunk carries no law, only section titles and page numbers, but it is
    dense with section numbers -- so Stage 2 reads it as a list of provisions and
    answers from pretrained knowledge instead of the excerpt. One constitution TOC
    fragment listing 'JUDICIAL SERVICE COMMISSION 111D ... 111E ...' produced a
    detailed answer about the Audit Service Commission under 153C/153D, a topic the
    excerpt never mentions. Cheaper to drop these than to detect the bad pair later.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    # Dotted leaders: "Meetings of the Commission ... .... .... 124"
    dotted = sum(1 for ln in lines if re.search(r"\.\s*\.\s*\.", ln))
    if dotted / len(lines) >= 0.30:
        return True
    # Or short entries that nearly all end in a bare page number.
    pagey = sum(1 for ln in lines if len(ln) < 90 and re.search(r"\s\d{1,4}\s*$", ln))
    return pagey / len(lines) >= 0.70


SKIP_NAMES = {
    ".gitkeep",
    "readme.md",
    "model_card.md",
    "dataset_lineage.md",
    "training_run_log.md",
}
# Not Sri Lankan primary sources — skip to keep Stage 1 tractable
SKIP_SUBSTRINGS = (
    "black's-law",
    "blacks-law",
    "black’s-law",
)

# Fallback classifier only — the manifest's subject_area column is the authoritative
# baseline (see resolve_subject). Order matters: the first match wins, so narrower
# subjects must precede broader ones (criminal_procedure before criminal_law,
# intellectual_property before property_land). Separators are matched with '.?' so
# patterns work on hyphenated filenames as well as spaced ones.
SUBJECT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"criminal.?procedure|code.?of.?criminal|bail", re.I), "criminal_procedure"),
    (re.compile(r"penal|crime|offence|drugs|poisons|opium", re.I), "criminal_law"),
    (re.compile(r"civil.?procedure", re.I), "civil_procedure"),
    (re.compile(r"constitution", re.I), "constitutional_law"),
    (re.compile(r"evidence", re.I), "evidence"),
    (re.compile(r"compan", re.I), "company_commercial"),
    (
        re.compile(r"intellectual|copyright|patent|trademark|geographical.?indication", re.I),
        "intellectual_property",
    ),
    (
        re.compile(
            r"marriage|maintenance|divorce|kandyan|muslim|domestic.?violence|family|adoption|custody",
            re.I,
        ),
        "family_law",
    ),
    (re.compile(r"sale.?of.?goods|consumer|contract", re.I), "contract_law"),
    (
        re.compile(r"registration.?of.?documents|trust|land|property|frauds|partition|notaries", re.I),
        "property_land",
    ),
    (re.compile(r"industrial|labour|labor|employ", re.I), "labour_industrial"),
    (
        re.compile(
            r"judicature|mediation|arbitration|primary.?court|data.?protection|right.?to.?information",
            re.I,
        ),
        "administrative_public",
    ),
    (re.compile(r"black.?s.?law|judgment|appeal", re.I), "case_law_methodology"),
]


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._parts))


def infer_subject(filename: str) -> str:
    for pattern, subject in SUBJECT_RULES:
        if pattern.search(filename):
            return subject
    return "administrative_public"


def load_manifest_subjects(manifest_path: Path) -> dict[str, str]:
    """Map filename -> subject_area from the manifest (the manual tagging baseline).

    Rows without a filename, and rows marked as duplicates, are skipped so they
    cannot be double counted in the subject-balance report.
    """
    if not manifest_path.exists():
        return {}
    mapping: dict[str, str] = {}
    with manifest_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            filename = (row.get("filename") or "").strip()
            subject = (row.get("subject_area") or "").strip()
            status = (row.get("download_status") or "").strip()
            if not filename or not subject or status.startswith("duplicate"):
                continue
            mapping[filename.lower()] = subject
    return mapping


def resolve_subject(filename: str, manifest_subjects: dict[str, str]) -> tuple[str, str]:
    """Return (subject_area, source).

    The manifest is authoritative; the filename regex is only a fallback for files
    that have not been tagged manually yet.
    """
    declared = manifest_subjects.get(filename.lower())
    if declared:
        return declared, "manifest"
    return infer_subject(filename), "filename_rule"


def list_source_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name.lower() in SKIP_NAMES:
            continue
        lowered = path.name.lower()
        if any(s in lowered for s in SKIP_SUBSTRINGS):
            print(f"[SKIP] {path.name} (excluded source)")
            continue
        if path.suffix.lower() in {".pdf", ".html", ".htm"}:
            files.append(path)
    return files


def extract_html_pages(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    parser = _HTMLTextExtractor()
    parser.feed(raw)
    text = parser.text().strip()
    return [{"page": 1, "text": text}]


def extract_pages_capped(pdf_path: Path, max_pages: int | None) -> list[dict[str, Any]]:
    """Like extract_pages, but stop after max_pages (keeps huge Acts usable on a laptop)."""
    import pdfplumber

    pages: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        limit = total if max_pages is None else min(total, max_pages)
        for i in range(limit):
            text = pdf.pages[i].extract_text() or ""
            pages.append({"page": i + 1, "text": text})
        if max_pages is not None and total > max_pages:
            pages.append(
                {
                    "page": limit + 1,
                    "text": f"[TRUNCATED: processed first {max_pages} of {total} pages]",
                }
            )
    return pages


def process_one(
    path: Path,
    doc_id: str,
    subject_area: str,
    cfg: dict[str, Any],
    cleaned_dir: Path,
    max_pages: int | None = 80,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    s1 = cfg["stage1"]
    hf_patterns = compile_patterns(s1["header_footer_patterns"])
    report: dict[str, Any] = {
        "doc_id": doc_id,
        "filename": path.name,
        "status": "OK",
        "errors": "",
        "warnings": "",
        "page_count": 0,
        "lines_stripped": 0,
        "units_detected": 0,
        "chunks_emitted": 0,
        "subject_area": subject_area,
        "processed_at": utc_now_iso(),
    }
    cleaned_text = ""
    chunks: list[dict[str, Any]] = []

    try:
        if path.suffix.lower() == ".pdf":
            pages = extract_pages_capped(path, max_pages)
        else:
            pages = extract_html_pages(path)

        report["page_count"] = len(pages)
        if not pages or all(not p["text"].strip() for p in pages):
            report["status"] = "FAIL"
            report["errors"] = "No extractable text"
            return [], report, cleaned_text

        lines, stripped = strip_headers_footers(pages, hf_patterns)
        report["lines_stripped"] = stripped
        cleaned_text = "\n".join(lines)
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        (cleaned_dir / f"{doc_id}.txt").write_text(cleaned_text, encoding="utf-8")

        if not lines:
            report["status"] = "FAIL"
            report["errors"] = "All text stripped as headers/footers"
            return [], report, cleaned_text

        units = detect_structure(lines, s1["structure_patterns"])
        report["units_detected"] = len(units)
        if not units:
            report["status"] = "FAIL"
            report["errors"] = "No structural units detected"
            return [], report, cleaned_text

        raw_chunks = chunk_units(
            units,
            min_chars=s1["min_chunk_chars"],
            max_chars=s1["max_chunk_chars"],
            merge_orphan_below=s1["merge_orphan_below_chars"],
        )
        warnings: list[str] = []
        toc_dropped = 0
        # A chunk that continues a section doesn't restate its number, so section_id
        # comes back None and section_heading degrades to the enclosing "PART II".
        # Stage 2 then has no idea which provision it is reading and supplies a number
        # from memory -- the single largest source of ungrounded citations measured on
        # this corpus. Carry the last known section forward and mark it as inherited so
        # Stage 2 can state it without guessing.
        last_section_id: str | None = None
        last_section_heading: str | None = None
        idx = 0
        for ch in raw_chunks:
            if looks_like_toc(ch["text"]):
                toc_dropped += 1
                continue

            own_id = ch.get("section_id")
            if own_id:
                last_section_id = own_id
                last_section_heading = ch.get("section_heading")
                inherited = False
            else:
                inherited = last_section_id is not None

            idx += 1
            chunk_id = f"{doc_id}-C{idx:04d}"
            if ch["char_count"] < s1["min_chunk_chars"]:
                warnings.append(f"{chunk_id} below min_chunk_chars ({ch['char_count']})")
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "source_file": path.name,
                    "subject_area": subject_area,
                    "title": path.stem,
                    "doc_type": "statute",
                    "section_id": own_id or (last_section_id if inherited else None),
                    "section_heading": ch.get("section_heading")
                    or (last_section_heading if inherited else None),
                    "section_inherited": inherited,
                    "chapter": ch.get("chapter"),
                    "part": ch.get("part"),
                    "text": ch["text"],
                    "char_count": ch["char_count"],
                    "schema_version": cfg["dataset"]["schema_version"],
                }
            )

        report["chunks_emitted"] = len(chunks)
        report["toc_chunks_dropped"] = toc_dropped
        if toc_dropped:
            warnings.append(f"{toc_dropped} table-of-contents chunk(s) dropped")
        report["warnings"] = " | ".join(warnings)
        if not chunks:
            report["status"] = "FAIL"
            report["errors"] = "Zero chunks emitted"
        elif warnings:
            report["status"] = "OK_WARN"

    except Exception as exc:  # noqa: BLE001
        report["status"] = "FAIL"
        report["errors"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()

    return chunks, report, cleaned_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1: parse/clean/chunk legal sources")
    parser.add_argument("--input_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--max_pages",
        type=int,
        default=80,
        help="Max PDF pages per file (default 80). Use 0 for no cap.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest CSV supplying the authoritative filename -> subject_area mapping "
        "(default: manifests/target_corpus_manifest.csv)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    input_dir = args.input_dir
    if not input_dir.is_absolute():
        input_dir = (ROOT / input_dir).resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = (ROOT / output_dir).resolve()

    if not input_dir.exists():
        # Convenience: raw_pdfs/ -> data/raw_pdfs/
        alt = ROOT / "data" / "raw_pdfs"
        if input_dir.name == "raw_pdfs" and alt.exists():
            input_dir = alt
        else:
            print(f"FAIL: input_dir not found: {input_dir}", file=sys.stderr)
            return 1

    files = list_source_files(input_dir)
    if not files:
        print(f"FAIL: no PDF/HTML sources in {input_dir}", file=sys.stderr)
        return 1

    cleaned_dir = output_dir / "cleaned_text"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    print(f"Input : {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Files : {len(files)}\n")

    max_pages = None if args.max_pages == 0 else args.max_pages
    print(f"max_pages per PDF: {max_pages if max_pages is not None else 'unlimited'}\n")

    manifest_path = args.manifest or (ROOT / "manifests" / "target_corpus_manifest.csv")
    if not manifest_path.is_absolute():
        manifest_path = (ROOT / manifest_path).resolve()
    manifest_subjects = load_manifest_subjects(manifest_path)
    if manifest_subjects:
        print(f"Manifest: {manifest_path.name} ({len(manifest_subjects)} tagged filenames)\n")
    else:
        print(f"Manifest: none usable at {manifest_path} - falling back to filename rules\n")

    untagged: list[str] = []

    for i, path in enumerate(files, start=1):
        doc_id = f"DOC-{i:03d}-{slugify(path.stem)[:40]}"
        subject, subject_source = resolve_subject(path.name, manifest_subjects)
        if subject_source == "filename_rule":
            untagged.append(path.name)
        print(f"--- ({i}/{len(files)}) {path.name} ---", flush=True)
        chunks, report, _ = process_one(
            path, doc_id, subject, cfg, cleaned_dir, max_pages=max_pages
        )
        report["subject_source"] = subject_source
        reports.append(report)
        all_chunks.extend(chunks)
        print(
            f"[{report['status']}] {path.name} | subject={subject} ({subject_source}) | "
            f"pages={report['page_count']} chunks={report['chunks_emitted']} "
            f"stripped={report['lines_stripped']}",
            flush=True,
        )
        if report["status"] == "FAIL":
            print(f"       errors: {report['errors']}", flush=True)

    chunks_path = output_dir / "chunks.jsonl"
    write_jsonl(chunks_path, all_chunks)

    report_csv = output_dir / "parse_report.csv"
    fields = [
        "doc_id",
        "filename",
        "status",
        "subject_area",
        "subject_source",
        "page_count",
        "lines_stripped",
        "units_detected",
        "chunks_emitted",
        "toc_chunks_dropped",
        "errors",
        "warnings",
        "processed_at",
    ]
    with report_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in reports:
            writer.writerow(r)

    write_json(
        output_dir / "stage1_summary.json",
        {
            "processed_at": utc_now_iso(),
            "documents_total": len(reports),
            "documents_ok": sum(1 for r in reports if str(r["status"]).startswith("OK")),
            "documents_failed": sum(1 for r in reports if r["status"] == "FAIL"),
            "chunks_total": len(all_chunks),
            "toc_chunks_dropped": sum(int(r.get("toc_chunks_dropped") or 0) for r in reports),
            "chunks_with_inherited_section": sum(
                1 for c in all_chunks if c.get("section_inherited")
            ),
            "chunks_without_section_id": sum(1 for c in all_chunks if not c.get("section_id")),
            "subject_from_manifest": sum(
                1 for r in reports if r.get("subject_source") == "manifest"
            ),
            "subject_from_filename_rule": len(untagged),
        },
    )

    failed = [r for r in reports if r["status"] == "FAIL"]
    print(f"\nWrote {chunks_path} ({len(all_chunks)} chunks)")
    print(f"Wrote {report_csv}")
    print(f"Cleaned text -> {cleaned_dir}")
    if untagged:
        print(
            f"\n*** {len(untagged)} file(s) not tagged in the manifest - subject guessed "
            "from the filename and may be wrong ***"
        )
        for name in untagged:
            print(f"  - {name}")
        print("  Add a manifest row (filename + subject_area) for each before trusting the balance report.")
    if failed:
        print(f"\n*** {len(failed)} FAIL row(s) in parse_report.csv — inspect before Stage 2 ***")
        for r in failed:
            print(f"  - {r['filename']}: {r['errors']}")
        return 0  # non-fatal: partial corpus may still proceed
    print("\nNo FAIL rows. Spot-check cleaned_text/ before Stage 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
