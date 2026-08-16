"""
Stage 3 — Split instruction pairs into train/val/test by whole source document
(not by individual pair) to prevent same-document leakage. Emit a subject-area
balance report that WARN when a subject is missing from val or test.
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import (
    PIPELINE_ROOT,
    load_config,
    read_jsonl,
    resolve_path,
    utc_now_iso,
    write_json,
    write_jsonl,
)


def assign_docs_to_splits(
    doc_ids: list[str],
    doc_subjects: dict[str, str],
    ratios: dict[str, float],
    seed: int,
) -> dict[str, str]:
    """
    Greedy subject-aware assignment: shuffle docs, fill test → val → train quotas
    while preferring to keep at least one doc per subject in val/test when possible.
    """
    rng = random.Random(seed)
    docs = list(doc_ids)
    rng.shuffle(docs)

    n = len(docs)
    n_test = max(1, round(n * ratios["test"])) if n >= 3 else (1 if n >= 2 else 0)
    n_val = max(1, round(n * ratios["val"])) if n >= 3 else (1 if n >= 2 else 0)
    # Ensure train gets the remainder and at least one when possible
    if n_test + n_val >= n and n >= 2:
        n_test = 1
        n_val = 1 if n >= 3 else 0
    n_train = n - n_test - n_val

    assignment: dict[str, str] = {}
    # Group by subject for stratified pick
    by_subject: dict[str, list[str]] = defaultdict(list)
    for d in docs:
        by_subject[doc_subjects[d]].append(d)

    # First pass: try to seed val and test with distinct subjects
    remaining = set(docs)
    subjects = list(by_subject.keys())
    rng.shuffle(subjects)

    def take_for(split: str, quota: int) -> None:
        taken = 0
        # Prefer uncovered subjects
        for subj in subjects:
            if taken >= quota:
                break
            candidates = [d for d in by_subject[subj] if d in remaining]
            if candidates:
                pick = candidates[0]
                assignment[pick] = split
                remaining.remove(pick)
                taken += 1
        # Fill remainder randomly
        pool = list(remaining)
        rng.shuffle(pool)
        for d in pool:
            if taken >= quota:
                break
            assignment[d] = split
            remaining.remove(d)
            taken += 1

    take_for("test", n_test)
    take_for("val", n_val)
    for d in list(remaining):
        assignment[d] = "train"

    # Sanity: if train empty but docs remain somehow, fix
    if n_train > 0 and not any(s == "train" for s in assignment.values()):
        # Move one from the largest non-train split
        for split in ("test", "val"):
            holders = [d for d, s in assignment.items() if s == split]
            if holders:
                assignment[holders[0]] = "train"
                break

    return assignment


def balance_report(
    pairs: list[dict[str, Any]],
    assignment: dict[str, str],
    warn_splits: list[str],
) -> dict[str, Any]:
    subjects = sorted({p["subject_area"] for p in pairs})
    splits = ("train", "val", "test")

    counts: dict[str, dict[str, int]] = {s: {subj: 0 for subj in subjects} for s in splits}
    doc_counts: dict[str, dict[str, int]] = {s: {subj: 0 for subj in subjects} for s in splits}
    docs_seen: dict[str, set[str]] = {s: set() for s in splits}

    for p in pairs:
        split = assignment[p["doc_id"]]
        counts[split][p["subject_area"]] += 1
        key = (p["doc_id"], p["subject_area"])
        if p["doc_id"] not in docs_seen[split]:
            docs_seen[split].add(p["doc_id"])
            doc_counts[split][p["subject_area"]] += 1

    warnings: list[str] = []
    for split in warn_splits:
        for subj in subjects:
            if counts[split][subj] == 0:
                warnings.append(
                    f"SUBJECT MISSING FROM {split.upper()}: '{subj}' has zero pairs. "
                    f"Consider adding another document in this subject before production training."
                )

    return {
        "pair_counts_by_split_and_subject": counts,
        "doc_counts_by_split_and_subject": doc_counts,
        "docs_per_split": {s: len(docs_seen[s]) for s in splits},
        "pairs_per_split": {
            s: sum(1 for p in pairs if assignment[p["doc_id"]] == s) for s in splits
        },
        "warnings": warnings,
    }


def to_sft_record(pair: dict[str, Any], split: str, dataset_version: str) -> dict[str, Any]:
    """Chat-style record suitable for Qwen instruction fine-tuning."""
    return {
        "pair_id": pair["pair_id"],
        "chunk_id": pair["chunk_id"],
        "doc_id": pair["doc_id"],
        "subject_area": pair["subject_area"],
        "pair_type": pair["pair_type"],
        "split": split,
        "dataset_version": dataset_version,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are LearnMateAI, a study assistant for Sri Lankan legal education. "
                    "Answer from the provided source excerpt. If the excerpt is insufficient, say so."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{pair['instruction']}\n\n---SOURCE EXCERPT---\n{pair['input']}"
                ),
            },
            {"role": "assistant", "content": pair["output"]},
        ],
    }


def run_stage3(cfg: dict[str, Any], dataset_version: str | None = None) -> dict[str, Any]:
    intermediate = resolve_path(cfg, "intermediate")
    output_dir = resolve_path(cfg, "output")
    reports_dir = resolve_path(cfg, "reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    pairs_path = intermediate / "stage2_pairs.jsonl"
    if not pairs_path.exists():
        raise FileNotFoundError(f"Missing Stage 2 output: {pairs_path}. Run stage2 first.")

    pairs = read_jsonl(pairs_path)
    if not pairs:
        raise RuntimeError("Stage 2 produced zero pairs.")

    doc_subjects: dict[str, str] = {}
    for p in pairs:
        doc_subjects.setdefault(p["doc_id"], p["subject_area"])

    assignment = assign_docs_to_splits(
        doc_ids=list(doc_subjects.keys()),
        doc_subjects=doc_subjects,
        ratios=cfg["stage3"]["ratios"],
        seed=cfg["stage3"]["random_seed"],
    )

    version = dataset_version or f"{cfg['dataset']['version_prefix']}-v{utc_now_iso()[:10]}"
    split_records: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    for p in pairs:
        split = assignment[p["doc_id"]]
        split_records[split].append(to_sft_record(p, split, version))

    for split, recs in split_records.items():
        write_jsonl(output_dir / f"{split}.jsonl", recs)

    # Also write a combined index for lineage
    write_json(
        output_dir / "split_assignment.json",
        {
            "dataset_version": version,
            "seed": cfg["stage3"]["random_seed"],
            "assignment": assignment,
        },
    )

    balance = balance_report(
        pairs, assignment, cfg["stage3"]["warn_missing_subject_in_splits"]
    )

    summary = {
        "stage": 3,
        "processed_at": utc_now_iso(),
        "dataset_version": version,
        "ratios": cfg["stage3"]["ratios"],
        "seed": cfg["stage3"]["random_seed"],
        "assignment": assignment,
        "balance": balance,
        "output_dir": str(output_dir.relative_to(PIPELINE_ROOT)),
    }
    write_json(reports_dir / "stage3_summary.json", summary)
    write_json(reports_dir / "subject_balance_report.json", balance)

    print(f"Stage 3 done - dataset_version={version}")
    for split in ("train", "val", "test"):
        print(f"  {split}: {len(split_records[split])} pairs")
    if balance["warnings"]:
        print("\n*** SUBJECT BALANCE WARNINGS ***")
        for w in balance["warnings"]:
            print(f"  ! {w}")
    else:
        print("  Subject balance: no missing-subject warnings.")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3: document-level train/val/test split")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dataset-version", type=str, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    summary = run_stage3(cfg, dataset_version=args.dataset_version)
    # Non-zero only on hard failure; warnings are informational
    return 0 if summary["balance"]["pairs_per_split"].get("train", 0) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
