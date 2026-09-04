"""Download comparison GGUFs or warm sentence-transformers caches. Weights stay out of git."""

from __future__ import annotations

import argparse
import sys

from common import ensure_backend_on_path, load_comparison_registry, models_dir

ensure_backend_on_path()

# Xet/hf_transfer has stalled mid-file on this Windows laptop. Plain HTTPS is enough.
import os
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

from learnmate import config
from learnmate.llm.download import ensure_gguf


def _fetch_gguf(entry: dict) -> str:
    dest = models_dir() / entry["gguf_path"]
    print(f"[*] GGUF {entry['id']} -> {dest}")
    return ensure_gguf(str(dest), entry.get("hf_repo") or "", entry.get("hf_file") or "")


def _warm_sentence_transformer(hf_id: str) -> None:
    from sentence_transformers import SentenceTransformer
    print(f"[*] Warm embedder {hf_id}")
    SentenceTransformer(hf_id)


def _warm_cross_encoder(hf_id: str) -> None:
    from sentence_transformers import CrossEncoder
    print(f"[*] Warm reranker {hf_id}")
    CrossEncoder(hf_id)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch comparison models. Default is embeddings+rerankers only.")
    parser.add_argument("--embeddings", action="store_true",
                        help="Download/warm all embedding candidates")
    parser.add_argument("--rerankers", action="store_true",
                        help="Download/warm all reranker candidates")
    parser.add_argument("--gguf", action="append", default=[],
                        help="Generator or judge id from comparison_registry.yaml (repeatable)")
    parser.add_argument("--all-gguf", action="store_true",
                        help="Download every comparison GGUF (~8 GB extra). Off by default.")
    args = parser.parse_args()

    registry = load_comparison_registry()
    want_st = args.embeddings or args.rerankers or not (args.gguf or args.all_gguf)

    if args.embeddings or want_st:
        for spec in registry["embeddings"]:
            _warm_sentence_transformer(spec["hf_id"])
    if args.rerankers or want_st:
        for spec in registry["rerankers"]:
            _warm_cross_encoder(spec["hf_id"])

    gguf_ids = set(args.gguf)
    if args.all_gguf:
        gguf_ids.update(e["id"] for e in registry["generators"])
        gguf_ids.update(e["id"] for e in registry["judges"])

    by_id = {}
    for group in ("generators", "judges"):
        for entry in registry[group]:
            by_id[entry["id"]] = entry

    for gid in gguf_ids:
        entry = by_id.get(gid)
        if entry is None:
            print(f"[!] unknown gguf id {gid!r}; known: {sorted(by_id)}", file=sys.stderr)
            sys.exit(2)
        _fetch_gguf(entry)

    print(f"[*] HF cache: {config.ROOT_DIR / 'data' / 'hf_cache'}")
    print(f"[*] GGUF dir: {models_dir()}")


if __name__ == "__main__":
    main()
