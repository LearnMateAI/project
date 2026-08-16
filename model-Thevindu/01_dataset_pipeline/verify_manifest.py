"""Manifest gate check — run before Stage 1.

Verifies three things the downstream balance report depends on:
  1. every manifest filename resolves to the subject_area the manifest declares
  2. no subject area is left with fewer than --min-docs documents (Step 1's gate)
  3. no filename is claimed by two rows

Usage:
  python verify_manifest.py
  python verify_manifest.py --manifest manifests/target_corpus_manifest.csv --min-docs 2
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from preprocess_dataset import infer_subject, load_manifest_subjects, resolve_subject  # noqa: E402

NON_DOCUMENT_TYPES = {"portal"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify manifest tagging and subject balance")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "manifests" / "target_corpus_manifest.csv",
    )
    parser.add_argument("--min-docs", type=int, default=2)
    args = parser.parse_args()

    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = (ROOT / manifest_path).resolve()
    if not manifest_path.exists():
        print(f"FAIL: manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    with manifest_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    manifest_subjects = load_manifest_subjects(manifest_path)
    failures: list[str] = []

    # 1. Manifest tagging is authoritative and self-consistent.
    fallback_disagrees: list[tuple[str, str, str]] = []
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for row in rows:
        filename = (row.get("filename") or "").strip()
        declared = (row.get("subject_area") or "").strip()
        status = (row.get("download_status") or "").strip()
        if not filename or status.startswith("duplicate"):
            continue
        if filename.lower() in seen:
            duplicates.append(f"{filename} claimed by {seen[filename.lower()]} and {row['doc_id']}")
        seen[filename.lower()] = row["doc_id"]

        resolved, source = resolve_subject(filename, manifest_subjects)
        if source != "manifest" or resolved != declared:
            failures.append(
                f"{row['doc_id']}: {filename} resolved to {resolved} ({source}) "
                f"but manifest declares {declared}"
            )
        guessed = infer_subject(filename)
        if guessed != declared:
            fallback_disagrees.append((row["doc_id"], declared, guessed))

    # 2. Subject balance across real documents only.
    counts: Counter[str] = Counter()
    by_subject: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        status = (row.get("download_status") or "").strip()
        if row.get("doc_type") in NON_DOCUMENT_TYPES or status.startswith("duplicate"):
            continue
        subject = (row.get("subject_area") or "").strip()
        counts[subject] += 1
        by_subject[subject].append(row["doc_id"])

    tier_counts = Counter(
        (r.get("source_tier") or "?").strip()
        for r in rows
        if r.get("doc_type") not in NON_DOCUMENT_TYPES
        and not (r.get("download_status") or "").startswith("duplicate")
    )

    print(f"Manifest: {manifest_path.name}")
    print(f"Rows: {len(rows)} | documents: {sum(counts.values())} | tagged filenames: {len(manifest_subjects)}")
    print(f"Source tiers: " + " ".join(f"{k}={v}" for k, v in sorted(tier_counts.items())))
    print()
    for subject, n in sorted(counts.items()):
        flag = "" if n >= args.min_docs else f"  << below min ({args.min_docs})"
        print(f"  {subject:24} {n}{flag}")

    thin = [s for s, n in counts.items() if n < args.min_docs]
    print()

    if fallback_disagrees:
        print(
            f"NOTE: {len(fallback_disagrees)} document(s) rely on the manifest baseline - "
            "the filename fallback alone would mis-tag them:"
        )
        for doc_id, declared, guessed in fallback_disagrees:
            print(f"  - {doc_id}: manifest={declared} vs filename_rule={guessed}")
        print()

    if duplicates:
        failures.extend(duplicates)
    if thin:
        failures.append(
            f"subject area(s) below {args.min_docs} documents: {', '.join(sorted(thin))}"
        )

    if failures:
        print(f"*** {len(failures)} FAILURE(S) ***")
        for f_ in failures:
            print(f"  - {f_}")
        return 1

    print("PASS: every filename resolves to its declared subject and no subject is below the minimum.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
