"""
Stage 2 CLI — LIVE (or mock) instruction-pair generation.

Usage:
  python generate_training_pairs.py --chunks_file processed/chunks.jsonl \\
      --output_file processed/pairs.jsonl --limit 20 --pairs_per_chunk 2

Reads OPENAI_API_KEY (or LM_API_KEY) from environment / .env — never hardcode keys.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from common import load_config, read_jsonl, utc_now_iso, write_json, write_jsonl  # noqa: E402
from stage2_generate_pairs import PAIR_PROMPTS, _stable_id, mock_pair  # noqa: E402


def resolve_api_key() -> str:
    load_dotenv(ROOT / ".env")
    key = os.getenv("OPENAI_API_KEY") or os.getenv("LM_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing API key. Set OPENAI_API_KEY in .env (gitignored) or the environment."
        )
    return key


def live_pair(
    chunk: dict[str, Any],
    pair_type: str,
    n: int,
    client: Any,
    model: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    system = PAIR_PROMPTS[pair_type]
    # Cap very long chunks to control cost/context
    excerpt = chunk["text"]
    if len(excerpt) > 6000:
        excerpt = excerpt[:6000] + "\n[...truncated for length...]"
    user = (
        f"Subject area: {chunk.get('subject_area')}\n"
        f"Heading: {chunk.get('section_heading')}\n\n"
        f"EXCERPT:\n{excerpt}"
    )
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"instruction": f"Explain: {chunk.get('section_heading')}", "output": raw}

    return {
        "pair_id": f"{chunk['chunk_id']}-{pair_type}-{n}-{_stable_id(chunk['chunk_id'], pair_type, str(n), model)}",
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "subject_area": chunk.get("subject_area", ""),
        "pair_type": pair_type,
        "instruction": parsed.get("instruction", ""),
        "input": chunk["text"],
        "output": parsed.get("output", ""),
        "generation_mode": "live",
        "model": model,
        "schema_version": chunk.get("schema_version", "1.0"),
        "created_at": utc_now_iso(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 2: generate training pairs")
    parser.add_argument("--chunks_file", type=Path, required=True)
    parser.add_argument("--output_file", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max chunks to process")
    parser.add_argument(
        "--pairs_per_chunk",
        type=int,
        default=2,
        help="Pairs per chunk (cycles qa/summary/mcq)",
    )
    parser.add_argument("--mock", action="store_true", help="No API calls")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    chunks_file = args.chunks_file if args.chunks_file.is_absolute() else ROOT / args.chunks_file
    output_file = args.output_file if args.output_file.is_absolute() else ROOT / args.output_file

    if not chunks_file.exists():
        print(f"FAIL: chunks file not found: {chunks_file}", file=sys.stderr)
        return 1

    chunks = read_jsonl(chunks_file)
    # Prefer longer, section-bearing chunks for quality sample
    chunks = sorted(chunks, key=lambda c: c.get("char_count", 0), reverse=True)
    if args.limit is not None:
        chunks = chunks[: args.limit]

    pair_types = cfg["stage2"]["pair_types"]
    types_cycle = [pair_types[i % len(pair_types)] for i in range(args.pairs_per_chunk)]

    client = None
    model = args.model or os.getenv("OPENAI_MODEL") or os.getenv("LM_MODEL") or cfg["stage2"]["api"]["default_model"]
    temperature = cfg["stage2"]["api"]["temperature"]
    max_tokens = cfg["stage2"]["api"]["max_tokens"]
    delay = 0.0

    if not args.mock:
        from openai import OpenAI

        api_key = resolve_api_key()
        client = OpenAI(api_key=api_key)
        delay = 60.0 / max(int(cfg["stage2"]["api"]["requests_per_minute"]), 1)
        print(f"LIVE mode | model={model} | chunks={len(chunks)} | pairs_per_chunk={args.pairs_per_chunk}")
        print("API key loaded from env/.env (not printed).")
    else:
        print(f"MOCK mode | chunks={len(chunks)}")

    pairs: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for ci, chunk in enumerate(chunks, start=1):
        for n, pair_type in enumerate(types_cycle, start=1):
            try:
                if args.mock:
                    pairs.append(mock_pair(chunk, pair_type, n))
                else:
                    pairs.append(
                        live_pair(chunk, pair_type, n, client, model, temperature, max_tokens)
                    )
                    time.sleep(delay)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "pair_type": pair_type,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                print(f"  ERROR {chunk.get('chunk_id')} {pair_type}: {exc}")
        if ci % 5 == 0 or ci == len(chunks):
            print(f"  progress {ci}/{len(chunks)} chunks -> {len(pairs)} pairs")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_file, pairs)
    write_json(
        output_file.with_suffix(".summary.json"),
        {
            "processed_at": utc_now_iso(),
            "mode": "mock" if args.mock else "live",
            "model": None if args.mock else model,
            "chunks_in": len(chunks),
            "pairs_out": len(pairs),
            "errors": errors,
            "limit": args.limit,
            "pairs_per_chunk": args.pairs_per_chunk,
        },
    )
    print(f"\nWrote {output_file} ({len(pairs)} pairs)")
    if errors:
        print(f"WARNING: {len(errors)} generation errors")
    print("CHECK: open pairs.jsonl and spot-read ~20-30 pairs for hallucinations before full batch.")
    return 0 if pairs else 1


if __name__ == "__main__":
    sys.exit(main())
