"""
Run the full three-stage pipeline end-to-end.

Default: sample PDFs + mock Stage 2 (no API cost) — used for smoke tests.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import load_config, resolve_path, utc_now_iso, write_json
from create_sample_pdfs import main as create_samples
from stage1_parse_chunk import run_stage1
from stage2_generate_pairs import run_stage2
from stage3_split_dataset import run_stage3


def main() -> int:
    parser = argparse.ArgumentParser(description="LearnMateAI dataset pipeline (all stages)")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--create-samples",
        action="store_true",
        help="Regenerate synthetic sample PDFs before Stage 1",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=None,
        help="PDF directory (default: sample_pdfs)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest CSV (default: sample_manifest.csv)",
    )
    parser.add_argument("--mock", action="store_true", default=False)
    parser.add_argument("--live", action="store_true", default=False)
    parser.add_argument("--dataset-version", type=str, default="lm-legal-smoke-v1")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.create_samples:
        print("=== Creating sample PDFs ===")
        create_samples()

    pdf_dir = args.pdf_dir or resolve_path(cfg, "sample_pdfs")
    manifest = args.manifest or resolve_path(cfg, "sample_manifest")

    print("\n=== Stage 1: Parse & Chunk ===")
    s1 = run_stage1(pdf_dir, manifest, cfg)
    if s1["chunks_total"] == 0:
        print("ABORT: Stage 1 produced no chunks.", file=sys.stderr)
        return 1

    mock = True
    if args.live:
        mock = False
    elif args.mock or cfg["stage2"].get("mock_mode_default", True):
        mock = True

    print(f"\n=== Stage 2: Generate Pairs ({'mock' if mock else 'live'}) ===")
    s2 = run_stage2(cfg, mock=mock)
    if s2["pairs_out"] == 0:
        print("ABORT: Stage 2 produced no pairs.", file=sys.stderr)
        return 1

    print("\n=== Stage 3: Split Dataset ===")
    s3 = run_stage3(cfg, dataset_version=args.dataset_version)

    overview = {
        "ran_at": utc_now_iso(),
        "dataset_version": args.dataset_version,
        "stage1": {
            "documents_ok": s1["documents_ok"],
            "documents_failed": s1["documents_failed"],
            "chunks_total": s1["chunks_total"],
        },
        "stage2": {
            "generation_mode": s2["generation_mode"],
            "pairs_out": s2["pairs_out"],
            "errors": len(s2["errors"]),
        },
        "stage3": {
            "pairs_per_split": s3["balance"]["pairs_per_split"],
            "warnings": s3["balance"]["warnings"],
        },
    }
    out = resolve_path(cfg, "reports") / "pipeline_run_summary.json"
    write_json(out, overview)
    print(f"\nPipeline complete. Summary -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
