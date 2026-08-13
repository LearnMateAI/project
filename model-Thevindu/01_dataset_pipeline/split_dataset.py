"""
Stage 3 CLI — subject-stratified train/val/test split + a strict held-out test set.

Two granularities, because they measure different things:

  --group_by document  Whole documents never span splits. Measures generalisation to
                       unseen legislation. Correct, but unusable on this corpus: with
                       19 documents of wildly unequal size (Criminal Procedure Code is
                       312 chunks, Registration of Documents is 16) and most subjects
                       holding a single document, a subject must land entirely in one
                       split. It left family_law and property_land with zero training
                       pairs and 8 subjects with no val or test at all.

  --group_by chapter   Units are (doc_id, chapter/part), 211 of them instead of 19, so
                       every subject reaches all three splits. Chapters of the same
                       statute may then appear in both train and test.

That leakage means chapter-split accuracy is NOT the accuracy in
acceptance_thresholds.yaml, which was written against unseen-document generalisation.
Record it as in_corpus_accuracy (chapter-held-out) and keep the names distinct -- a
candidate can clear the easier number without clearing the bar the threshold intended.

--strict_holdout reserves one whole document per subject that has two or more, written
to test_strict.jsonl and excluded from train/val/test at every granularity. It is small
and covers only part of the corpus, but it is a real generalisation signal to check the
chapter-split number against. If the two agree the leakage is doing little work; if they
diverge, that divergence is the finding.

Usage:
  python split_dataset.py --pairs_file processed_v01/pairs.jsonl \\
      --chunks_file processed_v01/chunks.jsonl --output_dir processed_v01/ \\
      --group_by chapter --strict_holdout \\
      --train 0.7 --val 0.15 --test 0.15 --dataset-version lm-legal-v0.1
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from common import load_config, read_jsonl, utc_now_iso, write_json, write_jsonl  # noqa: E402
from stage3_split_dataset import to_sft_record  # noqa: E402


def load_chunk_groups(chunks_file: Path) -> dict[str, str]:
    """chunk_id -> chapter/part label used to group related sections together."""
    groups: dict[str, str] = {}
    with chunks_file.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            c = json.loads(line)
            groups[c["chunk_id"]] = c.get("chapter") or c.get("part") or "_nogroup"
    return groups


def unit_key(pair: dict[str, Any], chunk_groups: dict[str, str], group_by: str) -> str:
    if group_by == "document":
        return pair["doc_id"]
    return f"{pair['doc_id']}::{chunk_groups.get(pair['chunk_id'], '_nogroup')}"


def pick_strict_holdout(
    pairs: list[dict[str, Any]],
    unit_of: Any,
    min_docs: int = 2,
    min_units_left: int = 3,
) -> tuple[dict[str, str], list[str]]:
    """subject -> doc_id reserved as a genuinely unseen document, plus skip reasons.

    Picks the smallest qualifying document per subject so the strict set costs as
    little training data as possible while still covering the subject.

    Skips a subject when removing that document would leave too few units to fill
    train, val and test -- otherwise the holdout recreates the very problem it sits
    alongside. family_law has exactly two documents, and reserving one initially left
    the other as a single unit that landed wholly in test, with nothing to train on.
    """
    per_subject_docs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in pairs:
        per_subject_docs[p.get("subject_area", "unknown")][p["doc_id"]] += 1

    holdout: dict[str, str] = {}
    skipped: list[str] = []
    for subject, docs in sorted(per_subject_docs.items()):
        if len(docs) < min_docs:
            continue
        candidate = min(sorted(docs.items()), key=lambda kv: kv[1])[0]
        remaining_units = {
            unit_of(p) for p in pairs
            if p.get("subject_area") == subject and p["doc_id"] != candidate
        }
        if len(remaining_units) < min_units_left:
            skipped.append(
                f"{subject}: holding out {candidate} would leave only "
                f"{len(remaining_units)} unit(s) to cover train/val/test"
            )
            continue
        holdout[subject] = candidate
    return holdout, skipped


def stratified_assign(
    units: dict[str, list[dict[str, Any]]],
    unit_subject: dict[str, str],
    ratios: dict[str, float],
    seed: int,
) -> dict[str, str]:
    """Assign whole units to splits, balancing within each subject independently.

    Global greedy assignment skews badly when unit sizes differ by an order of
    magnitude -- one 312-chunk statute swamped val at 80% of a single subject. Filling
    each subject's own quota keeps every subject present in every split.
    """
    rng = random.Random(seed)
    by_subject: dict[str, list[str]] = defaultdict(list)
    for key, subject in unit_subject.items():
        by_subject[subject].append(key)

    assignment: dict[str, str] = {}
    for subject in sorted(by_subject):
        keys = sorted(by_subject[subject])
        rng.shuffle(keys)
        # Largest units first: packing big ones before small leaves the small units free
        # to correct the residual, which lands much closer to the target ratio.
        keys.sort(key=lambda k: len(units[k]), reverse=True)
        total_pairs = sum(len(units[k]) for k in keys)
        quota = {s: total_pairs * r for s, r in ratios.items()}

        # Fill whichever split is furthest below quota. Filling test first, as an earlier
        # version did, sent every unit of a small subject to test and left train empty.
        got = {"train": 0, "val": 0, "test": 0}
        counts = {"train": 0, "val": 0, "test": 0}
        for key in keys:
            target = max(quota, key=lambda s: quota[s] - got[s])
            assignment[key] = target
            got[target] += len(units[key])
            counts[target] += 1

        # With enough units, guarantee presence rather than leaving a split empty:
        # donate the smallest unit from whichever split has the biggest surplus.
        if len(keys) >= 3:
            for split in ("train", "val", "test"):
                if counts[split]:
                    continue
                donor = max(
                    (s for s in counts if counts[s] > 1),
                    key=lambda s: got[s] - quota[s],
                    default=None,
                )
                if donor is None:
                    continue
                movable = min(
                    (k for k in keys if assignment[k] == donor), key=lambda k: len(units[k])
                )
                assignment[movable] = split
                got[donor] -= len(units[movable])
                got[split] += len(units[movable])
                counts[donor] -= 1
                counts[split] += 1
    return assignment


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3: stratified dataset split")
    parser.add_argument("--pairs_file", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--chunks_file", type=Path, default=None,
                        help="Required for --group_by chapter; supplies chapter/part labels.")
    parser.add_argument("--group_by", choices=("document", "chapter"), default="document")
    parser.add_argument("--strict_holdout", action="store_true",
                        help="Reserve one whole document per multi-document subject as "
                             "test_strict.jsonl, unseen at any granularity.")
    parser.add_argument("--train", type=float, default=0.8)
    parser.add_argument("--val", type=float, default=0.1)
    parser.add_argument("--test", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dataset-version", type=str, default=None)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    total = args.train + args.val + args.test
    if abs(total - 1.0) > 1e-6:
        print(f"FAIL: train+val+test must sum to 1.0 (got {total})", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    pairs_file = args.pairs_file if args.pairs_file.is_absolute() else ROOT / args.pairs_file
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pairs_file.exists():
        print(f"FAIL: pairs file not found: {pairs_file}", file=sys.stderr)
        return 1

    pairs = read_jsonl(pairs_file)
    if not pairs:
        print("FAIL: zero pairs", file=sys.stderr)
        return 1

    chunk_groups: dict[str, str] = {}
    if args.group_by == "chapter":
        if args.chunks_file is None:
            print("FAIL: --group_by chapter requires --chunks_file", file=sys.stderr)
            return 1
        cf = args.chunks_file if args.chunks_file.is_absolute() else ROOT / args.chunks_file
        if not cf.exists():
            print(f"FAIL: chunks file not found: {cf}", file=sys.stderr)
            return 1
        chunk_groups = load_chunk_groups(cf)

    version = args.dataset_version or f"lm-legal-v{utc_now_iso()[:10]}"
    seed = args.seed if args.seed is not None else cfg["stage3"]["random_seed"]

    strict_docs: dict[str, str] = {}
    strict_skipped: list[str] = []
    strict_pairs: list[dict[str, Any]] = []
    if args.strict_holdout:
        strict_docs, strict_skipped = pick_strict_holdout(
            pairs, lambda p: unit_key(p, chunk_groups, args.group_by)
        )
        reserved = set(strict_docs.values())
        strict_pairs = [p for p in pairs if p["doc_id"] in reserved]
        pairs = [p for p in pairs if p["doc_id"] not in reserved]

    units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unit_subject: dict[str, str] = {}
    for p in pairs:
        key = unit_key(p, chunk_groups, args.group_by)
        units[key].append(p)
        unit_subject.setdefault(key, p.get("subject_area", "unknown"))

    assignment = stratified_assign(
        units, unit_subject,
        {"train": args.train, "val": args.val, "test": args.test},
        seed,
    )

    split_records: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    for key, group in units.items():
        split = assignment[key]
        for p in group:
            split_records[split].append(to_sft_record(p, split, version))

    for split, recs in split_records.items():
        write_jsonl(output_dir / f"{split}.jsonl", recs)

    if args.strict_holdout:
        write_jsonl(
            output_dir / "test_strict.jsonl",
            [to_sft_record(p, "test_strict", version) for p in strict_pairs],
        )

    write_json(
        output_dir / "split_assignment.json",
        {
            "dataset_version": version,
            "seed": seed,
            "group_by": args.group_by,
            "units": len(units),
            "strict_holdout_docs": strict_docs,
            "strict_holdout_skipped": strict_skipped,
            "metric_name": (
                "in_corpus_accuracy (chapter-held-out)"
                if args.group_by == "chapter"
                else "accuracy (document-held-out)"
            ),
            "assignment": assignment,
        },
    )

    # Per-subject pair counts, including the strict set so gaps are visible in one place.
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for split, recs in split_records.items():
        for r in recs:
            counts[r.get("subject_area", "unknown")][split] += 1
    for p in strict_pairs:
        counts[p.get("subject_area", "unknown")]["test_strict"] += 1

    report_csv = output_dir / "split_report.csv"
    warnings: list[str] = []
    with report_csv.open("w", encoding="utf-8", newline="") as f:
        fields = ["subject_area", "train_pairs", "val_pairs", "test_pairs",
                  "test_strict_pairs", "missing_in"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for subj in sorted(counts):
            row = counts[subj]
            missing = [s for s in ("train", "val", "test") if row.get(s, 0) == 0]
            if missing:
                warnings.append(f"{subj} missing from: {', '.join(missing)}")
            writer.writerow({
                "subject_area": subj,
                "train_pairs": row.get("train", 0),
                "val_pairs": row.get("val", 0),
                "test_pairs": row.get("test", 0),
                "test_strict_pairs": row.get("test_strict", 0),
                "missing_in": "|".join(missing),
            })

    write_json(output_dir / "subject_balance_report.json",
               {"dataset_version": version, "group_by": args.group_by,
                "counts_by_subject": {k: dict(v) for k, v in counts.items()},
                "warnings": warnings})

    print(f"dataset_version={version}  group_by={args.group_by}  units={len(units)}")
    for split in ("train", "val", "test"):
        print(f"  {split:11s}: {len(split_records[split]):5d} pairs")
    if args.strict_holdout:
        print(f"  test_strict: {len(strict_pairs):5d} pairs "
              f"({len(strict_docs)} whole documents, unseen at any granularity)")
        for subject, doc in sorted(strict_docs.items()):
            print(f"        {subject:22s} <- {doc}")
        for reason in strict_skipped:
            print(f"        SKIPPED {reason}")
    print(f"Wrote {report_csv}")
    if warnings:
        print("\n*** SUBJECT BALANCE WARNINGS ***")
        for w in warnings:
            print(f"  ! {w}")
    else:
        print("Subject balance: every subject present in train, val and test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
