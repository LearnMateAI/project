"""
Stage 3 CLI — whole-document train/val/test split + subject balance report.

Usage:
  python split_dataset.py --pairs_file processed/pairs.jsonl \\
      --output_dir processed/ --train 0.8 --val 0.1 --test 0.1
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from common import load_config, read_jsonl, utc_now_iso, write_json, write_jsonl  # noqa: E402
from stage3_split_dataset import (  # noqa: E402
    assign_docs_to_splits,
    balance_report,
    to_sft_record,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3: document-level dataset split")
    parser.add_argument("--pairs_file", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
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

    doc_subjects: dict[str, str] = {}
    for p in pairs:
        doc_subjects.setdefault(p["doc_id"], p.get("subject_area", "unknown"))

    seed = args.seed if args.seed is not None else cfg["stage3"]["random_seed"]
    assignment = assign_docs_to_splits(
        doc_ids=list(doc_subjects.keys()),
        doc_subjects=doc_subjects,
        ratios={"train": args.train, "val": args.val, "test": args.test},
        seed=seed,
    )

    version = args.dataset_version or f"lm-legal-v{utc_now_iso()[:10]}"
    split_records = {"train": [], "val": [], "test": []}
    for p in pairs:
        split = assignment[p["doc_id"]]
        split_records[split].append(to_sft_record(p, split, version))

    for split, recs in split_records.items():
        write_jsonl(output_dir / f"{split}.jsonl", recs)

    write_json(
        output_dir / "split_assignment.json",
        {"dataset_version": version, "seed": seed, "assignment": assignment},
    )

    balance = balance_report(
        pairs, assignment, cfg["stage3"]["warn_missing_subject_in_splits"]
    )

    # Flat CSV for quick human check
    subjects = sorted({p.get("subject_area", "unknown") for p in pairs})
    report_csv = output_dir / "split_report.csv"
    with report_csv.open("w", encoding="utf-8", newline="") as f:
        fields = ["subject_area", "train_pairs", "val_pairs", "test_pairs", "missing_in"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for subj in subjects:
            tr = balance["pair_counts_by_split_and_subject"]["train"].get(subj, 0)
            va = balance["pair_counts_by_split_and_subject"]["val"].get(subj, 0)
            te = balance["pair_counts_by_split_and_subject"]["test"].get(subj, 0)
            missing = []
            if va == 0:
                missing.append("val")
            if te == 0:
                missing.append("test")
            writer.writerow(
                {
                    "subject_area": subj,
                    "train_pairs": tr,
                    "val_pairs": va,
                    "test_pairs": te,
                    "missing_in": "|".join(missing),
                }
            )

    write_json(output_dir / "subject_balance_report.json", balance)

    print(f"dataset_version={version}")
    for split in ("train", "val", "test"):
        print(f"  {split}: {len(split_records[split])} pairs")
    print(f"Wrote {report_csv}")
    if balance["warnings"]:
        print("\n*** SUBJECT BALANCE WARNINGS ***")
        for w in balance["warnings"]:
            print(f"  ! {w}")
        print(
            "At real-corpus scale this is common — manually move a document or two "
            "in split_assignment.json rather than re-rolling the seed."
        )
    else:
        print("Subject balance: no missing-subject warnings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
