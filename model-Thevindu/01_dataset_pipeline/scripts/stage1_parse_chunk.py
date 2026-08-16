"""
Stage 1 — Parse PDFs, clean headers/footers, detect statutory structure,
chunk on section/clause boundaries, tag subject area, emit per-document reports.
"""
from __future__ import annotations

import argparse
import re
import sys
import traceback
from pathlib import Path
from typing import Any

import pdfplumber

from common import (
    PIPELINE_ROOT,
    compile_patterns,
    load_config,
    load_manifest,
    resolve_path,
    utc_now_iso,
    write_json,
    write_jsonl,
)


def extract_pages(pdf_path: Path) -> list[dict[str, Any]]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": i, "text": text})
    return pages


def strip_headers_footers(
    pages: list[dict[str, Any]], patterns: list[re.Pattern[str]]
) -> tuple[list[str], int]:
    """Remove lines matching header/footer/page-number patterns. Returns cleaned lines + strip count."""
    cleaned_lines: list[str] = []
    stripped = 0
    for page in pages:
        for raw in page["text"].splitlines():
            line = raw.strip()
            if not line:
                continue
            if any(p.match(line) for p in patterns):
                stripped += 1
                continue
            cleaned_lines.append(line)
    return cleaned_lines, stripped


def detect_structure(
    lines: list[str], structure_patterns: dict[str, str]
) -> list[dict[str, Any]]:
    """
    Walk lines and emit structural units. New chapter/part/section starts a unit;
    following body lines accumulate until the next boundary.
    """
    compiled = {k: re.compile(v) for k, v in structure_patterns.items()}
    units: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    context = {"chapter": None, "part": None}

    def flush() -> None:
        nonlocal current
        if current and current["text"].strip():
            units.append(current)
        current = None

    for line in lines:
        matched_kind = None
        match = None
        for kind in ("chapter", "part", "section"):
            m = compiled[kind].match(line)
            if m:
                matched_kind = kind
                match = m
                break

        if matched_kind in {"chapter", "part"}:
            flush()
            context[matched_kind] = line.strip()
            if matched_kind == "chapter":
                context["part"] = None
            continue

        if matched_kind == "section":
            flush()
            sec_id = match.group(1)
            sec_title = match.group(2).strip()
            current = {
                "section_id": sec_id,
                "section_heading": f"{sec_id}. {sec_title[:120]}",
                "chapter": context["chapter"],
                "part": context["part"],
                "text": line.strip(),
            }
            continue

        # Body / subsection lines attach to current section unit
        if current is None:
            current = {
                "section_id": None,
                "section_heading": context.get("chapter") or context.get("part") or "preamble",
                "chapter": context["chapter"],
                "part": context["part"],
                "text": line.strip(),
            }
        else:
            current["text"] += "\n" + line.strip()

    flush()
    return units


def chunk_units(
    units: list[dict[str, Any]],
    min_chars: int,
    max_chars: int,
    merge_orphan_below: int,
) -> list[dict[str, Any]]:
    """
    Semantic chunking on section boundaries (not fixed windows).
    Oversized sections are split on paragraph breaks; tiny orphans merge into previous.
    """
    chunks: list[dict[str, Any]] = []

    for unit in units:
        text = unit["text"].strip()
        if not text:
            continue

        if len(text) <= max_chars:
            pieces = [text]
        else:
            paras = [p.strip() for p in re.split(r"\n{2,}|\n", text) if p.strip()]
            pieces = []
            buf = ""
            for para in paras:
                if not buf:
                    buf = para
                elif len(buf) + 1 + len(para) <= max_chars:
                    buf = buf + "\n" + para
                else:
                    pieces.append(buf)
                    buf = para
            if buf:
                pieces.append(buf)

        for i, piece in enumerate(pieces):
            chunk = {
                "section_id": unit.get("section_id"),
                "section_heading": unit.get("section_heading"),
                "chapter": unit.get("chapter"),
                "part": unit.get("part"),
                "text": piece,
                "char_count": len(piece),
                "part_index": i,
            }
            if (
                chunks
                and chunk["char_count"] < merge_orphan_below
                and chunks[-1]["char_count"] + 1 + chunk["char_count"] <= max_chars
            ):
                chunks[-1]["text"] += "\n" + chunk["text"]
                chunks[-1]["char_count"] = len(chunks[-1]["text"])
            elif chunk["char_count"] >= min_chars or not chunks:
                chunks.append(chunk)
            else:
                # Below min but no previous — keep anyway, flag later
                chunks.append(chunk)

    return chunks


def process_document(
    pdf_path: Path,
    doc_meta: dict[str, Any],
    cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    s1 = cfg["stage1"]
    hf_patterns = compile_patterns(s1["header_footer_patterns"])

    report: dict[str, Any] = {
        "doc_id": doc_meta["doc_id"],
        "filename": pdf_path.name,
        "status": "ok",
        "errors": [],
        "warnings": [],
        "page_count": 0,
        "lines_stripped": 0,
        "units_detected": 0,
        "chunks_emitted": 0,
        "subject_area": doc_meta["subject_area"],
        "processed_at": utc_now_iso(),
    }

    try:
        pages = extract_pages(pdf_path)
        report["page_count"] = len(pages)
        if not pages or all(not p["text"].strip() for p in pages):
            report["status"] = "failed"
            report["errors"].append("No extractable text (empty or image-only PDF)")
            return [], report

        lines, stripped = strip_headers_footers(pages, hf_patterns)
        report["lines_stripped"] = stripped
        if not lines:
            report["status"] = "failed"
            report["errors"].append("All text stripped as headers/footers — check patterns")
            return [], report

        units = detect_structure(lines, s1["structure_patterns"])
        report["units_detected"] = len(units)
        if not units:
            report["status"] = "failed"
            report["errors"].append("No structural units detected")
            return [], report

        raw_chunks = chunk_units(
            units,
            min_chars=s1["min_chunk_chars"],
            max_chars=s1["max_chunk_chars"],
            merge_orphan_below=s1["merge_orphan_below_chars"],
        )

        chunks = []
        for idx, ch in enumerate(raw_chunks, start=1):
            chunk_id = f"{doc_meta['doc_id']}-C{idx:04d}"
            if ch["char_count"] < s1["min_chunk_chars"]:
                report["warnings"].append(
                    f"{chunk_id} below min_chunk_chars ({ch['char_count']})"
                )
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_meta["doc_id"],
                    "source_file": pdf_path.name,
                    "subject_area": doc_meta["subject_area"],
                    "title": doc_meta.get("title", ""),
                    "doc_type": doc_meta.get("doc_type", ""),
                    "section_id": ch.get("section_id"),
                    "section_heading": ch.get("section_heading"),
                    "chapter": ch.get("chapter"),
                    "part": ch.get("part"),
                    "text": ch["text"],
                    "char_count": ch["char_count"],
                    "schema_version": cfg["dataset"]["schema_version"],
                }
            )

        report["chunks_emitted"] = len(chunks)
        if not chunks:
            report["status"] = "failed"
            report["errors"].append("Structure detected but zero chunks emitted")
        elif report["warnings"]:
            report["status"] = "ok_with_warnings"

    except Exception as exc:  # noqa: BLE001 — surface failures in report, don't abort corpus
        report["status"] = "failed"
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()
        return [], report

    return chunks, report


def run_stage1(
    pdf_dir: Path,
    manifest_path: Path,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    intermediate = resolve_path(cfg, "intermediate")
    reports_dir = resolve_path(cfg, "reports")
    intermediate.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Map filename → meta; require filename column for local PDFs
    if "filename" not in manifest.columns:
        raise ValueError(
            "Stage 1 local run requires a 'filename' column in the manifest "
            "(use sample_manifest.csv or add filenames for downloaded PDFs)."
        )

    all_chunks: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    for _, row in manifest.iterrows():
        meta = row.to_dict()
        pdf_path = pdf_dir / meta["filename"]
        if not pdf_path.exists():
            report = {
                "doc_id": meta["doc_id"],
                "filename": meta["filename"],
                "status": "failed",
                "errors": [f"File not found: {pdf_path}"],
                "warnings": [],
                "page_count": 0,
                "lines_stripped": 0,
                "units_detected": 0,
                "chunks_emitted": 0,
                "subject_area": meta["subject_area"],
                "processed_at": utc_now_iso(),
            }
            reports.append(report)
            write_json(reports_dir / f"parse_{meta['doc_id']}.json", report)
            print(f"[FAIL] {meta['doc_id']} — file not found")
            continue

        chunks, report = process_document(pdf_path, meta, cfg)
        reports.append(report)
        write_json(reports_dir / f"parse_{meta['doc_id']}.json", report)
        all_chunks.extend(chunks)
        print(
            f"[{report['status'].upper()}] {meta['doc_id']} — "
            f"{report['chunks_emitted']} chunks, {report['lines_stripped']} lines stripped"
        )

    chunks_path = intermediate / "stage1_chunks.jsonl"
    write_jsonl(chunks_path, all_chunks)

    summary = {
        "stage": 1,
        "processed_at": utc_now_iso(),
        "documents_total": len(manifest),
        "documents_ok": sum(1 for r in reports if r["status"].startswith("ok")),
        "documents_failed": sum(1 for r in reports if r["status"] == "failed"),
        "chunks_total": len(all_chunks),
        "chunks_path": str(chunks_path.relative_to(PIPELINE_ROOT)),
        "reports": reports,
    }
    write_json(reports_dir / "stage1_summary.json", summary)
    print(
        f"\nStage 1 done: {summary['documents_ok']}/{summary['documents_total']} ok, "
        f"{summary['chunks_total']} chunks -> {chunks_path}"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1: parse & chunk legal PDFs")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=None,
        help="Directory of PDFs (default: sample_pdfs)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest CSV (default: sample_manifest.csv)",
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    pdf_dir = args.pdf_dir or resolve_path(cfg, "sample_pdfs")
    manifest = args.manifest or resolve_path(cfg, "sample_manifest")
    summary = run_stage1(pdf_dir, manifest, cfg)
    return 1 if summary["documents_failed"] == summary["documents_total"] else 0


if __name__ == "__main__":
    sys.exit(main())
