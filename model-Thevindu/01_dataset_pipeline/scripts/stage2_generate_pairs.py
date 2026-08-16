"""
Stage 2 — Convert Stage 1 chunks into instruction-format training pairs
(Q&A, summary, MCQ). Each pair is traceable to its source chunk_id.

Supports:
  --mock   deterministic template pairs (no API cost; used for smoke tests)
  live     OpenAI-compatible API via LM_API_KEY / LM_API_BASE / LM_MODEL
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from common import (
    PIPELINE_ROOT,
    load_config,
    read_jsonl,
    resolve_path,
    utc_now_iso,
    write_json,
    write_jsonl,
)

# Measured on the real corpus: 38% of generated pairs cited a section number the
# excerpt did not contain. The old summary prompt said "preserving section numbers",
# which on a chunk that starts mid-section (no number visible) invited the model to
# supply one from memory -- 12 of the 15 bad pairs were summaries. This rule is stated
# first, in the same words, in every prompt.
_CITATION_RULE = (
    "CITATION RULE (strict): you may state a section, article, chapter or rule "
    "number ONLY if that exact number appears literally in the excerpt, or is given "
    "to you above as the section this excerpt belongs to. If the excerpt starts "
    "mid-provision and no number is shown, write \"this section\" or \"this "
    "provision\" instead. Never number a provision from your own knowledge of Sri "
    "Lankan law, and never list neighbouring section numbers that are not in the "
    "excerpt. A correct answer with no numbers is better than an invented citation.\n\n"
)

PAIR_PROMPTS = {
    "qa": (
        "You are drafting study Q&A for Sri Lankan law students. "
        "Using ONLY the statutory/case excerpt below, write one clear question "
        "and a grounded answer. Do not invent sections or facts not present.\n\n"
        + _CITATION_RULE
        + "Return JSON: {\"instruction\": \"...\", \"output\": \"...\"}"
    ),
    "summary": (
        "You are drafting study summaries for Sri Lankan law students. "
        "Summarise the excerpt below in 3–5 sentences, preserving the legal tests it "
        "sets out. Do not add external law.\n\n"
        + _CITATION_RULE
        + "Return JSON: {\"instruction\": \"Summarise the following legal text.\", \"output\": \"...\"}"
    ),
    "mcq": (
        "You are drafting a multiple-choice question for Sri Lankan law students. "
        "Using ONLY the excerpt below, write one MCQ with four options (A–D) and "
        "indicate the correct option with a one-sentence justification grounded in the text.\n\n"
        + _CITATION_RULE
        + "Return JSON: {\"instruction\": \"...\", \"output\": \"...\"}"
    ),
}


def _stable_id(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return h


def mock_pair(chunk: dict[str, Any], pair_type: str, n: int) -> dict[str, Any]:
    """Deterministic, structurally valid instruction pairs for offline smoke tests."""
    text = chunk["text"]
    heading = chunk.get("section_heading") or chunk.get("chapter") or "the excerpt"
    subject = chunk["subject_area"]
    snippet = text[:280].replace("\n", " ")

    if pair_type == "qa":
        instruction = (
            f"[{subject}] Based on {heading}, what does the provision establish?"
        )
        output = (
            f"According to the source text ({heading}): {snippet}"
            f"{'...' if len(text) > 280 else ''}"
        )
    elif pair_type == "summary":
        instruction = "Summarise the following legal text for a law student."
        output = (
            f"Subject area: {subject}. Heading: {heading}. "
            f"Key content: {snippet}{'...' if len(text) > 280 else ''}"
        )
    else:  # mcq
        instruction = (
            f"[{subject}] Which statement best reflects {heading}?\n"
            f"A. The provision is unrelated to {subject}.\n"
            f"B. The provision addresses the matter described in the source excerpt.\n"
            f"C. The provision abolishes all prior law without exception.\n"
            f"D. The provision applies only outside Sri Lanka."
        )
        output = (
            "Correct answer: B. "
            f"Justification grounded in source ({heading}): {snippet}"
            f"{'...' if len(text) > 280 else ''}"
        )

    pair_id = f"{chunk['chunk_id']}-{pair_type}-{n}-{_stable_id(chunk['chunk_id'], pair_type, str(n))}"
    return {
        "pair_id": pair_id,
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "subject_area": subject,
        "pair_type": pair_type,
        "instruction": instruction,
        "input": text,
        "output": output,
        "generation_mode": "mock",
        "schema_version": chunk.get("schema_version", "1.0"),
        "created_at": utc_now_iso(),
    }


def _get_client(cfg: dict[str, Any]):
    from openai import OpenAI

    api_cfg = cfg["stage2"]["api"]
    api_key = os.getenv(api_cfg["env_api_key"])
    if not api_key:
        raise RuntimeError(
            f"Live mode requires ${api_cfg['env_api_key']} in the environment or .env"
        )
    base = os.getenv(api_cfg["env_api_base"]) or None
    return OpenAI(api_key=api_key, base_url=base), api_cfg


def live_pair(
    chunk: dict[str, Any],
    pair_type: str,
    n: int,
    client: Any,
    api_cfg: dict[str, Any],
) -> dict[str, Any]:
    model = os.getenv(api_cfg["env_model"]) or api_cfg["default_model"]
    system = PAIR_PROMPTS[pair_type]
    user = (
        f"Subject area: {chunk['subject_area']}\n"
        f"Heading: {chunk.get('section_heading')}\n\n"
        f"EXCERPT:\n{chunk['text']}"
    )
    resp = client.chat.completions.create(
        model=model,
        temperature=api_cfg["temperature"],
        max_tokens=api_cfg["max_tokens"],
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

    pair_id = f"{chunk['chunk_id']}-{pair_type}-{n}-{_stable_id(chunk['chunk_id'], pair_type, str(n), model)}"
    return {
        "pair_id": pair_id,
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "subject_area": chunk["subject_area"],
        "pair_type": pair_type,
        "instruction": parsed.get("instruction", ""),
        "input": chunk["text"],
        "output": parsed.get("output", ""),
        "generation_mode": "live",
        "model": model,
        "schema_version": chunk.get("schema_version", "1.0"),
        "created_at": utc_now_iso(),
    }


def run_stage2(cfg: dict[str, Any], mock: bool) -> dict[str, Any]:
    load_dotenv(PIPELINE_ROOT / ".env")
    intermediate = resolve_path(cfg, "intermediate")
    reports_dir = resolve_path(cfg, "reports")
    chunks_path = intermediate / "stage1_chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"Missing Stage 1 output: {chunks_path}. Run stage1 first.")

    chunks = read_jsonl(chunks_path)
    pair_types = cfg["stage2"]["pair_types"]
    per_type = cfg["stage2"]["pairs_per_type"]

    client = None
    api_cfg = None
    if not mock:
        client, api_cfg = _get_client(cfg)
        rpm = api_cfg["requests_per_minute"]
        delay = 60.0 / max(rpm, 1)
    else:
        delay = 0

    pairs: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for chunk in chunks:
        for pair_type in pair_types:
            for n in range(1, per_type + 1):
                try:
                    if mock:
                        pairs.append(mock_pair(chunk, pair_type, n))
                    else:
                        pairs.append(live_pair(chunk, pair_type, n, client, api_cfg))
                        time.sleep(delay)
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        {
                            "chunk_id": chunk["chunk_id"],
                            "pair_type": pair_type,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )

    out_path = intermediate / "stage2_pairs.jsonl"
    write_jsonl(out_path, pairs)

    summary = {
        "stage": 2,
        "processed_at": utc_now_iso(),
        "generation_mode": "mock" if mock else "live",
        "chunks_in": len(chunks),
        "pairs_out": len(pairs),
        "errors": errors,
        "pairs_path": str(out_path.relative_to(PIPELINE_ROOT)),
        "pair_type_counts": {
            t: sum(1 for p in pairs if p["pair_type"] == t) for t in pair_types
        },
    }
    write_json(reports_dir / "stage2_summary.json", summary)
    print(
        f"Stage 2 done ({summary['generation_mode']}): "
        f"{summary['pairs_out']} pairs from {summary['chunks_in']} chunks -> {out_path}"
    )
    if errors:
        print(f"  WARNING: {len(errors)} pair generation errors (see stage2_summary.json)")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 2: generate instruction pairs")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic mock pairs (no API calls)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call LLM API (requires LM_API_KEY)",
    )
    args = parser.parse_args()
    cfg = load_config(args.config)

    if args.live and args.mock:
        print("Choose either --mock or --live, not both", file=sys.stderr)
        return 2
    mock = args.mock or (not args.live and cfg["stage2"].get("mock_mode_default", True))
    if args.live:
        mock = False

    summary = run_stage2(cfg, mock=mock)
    return 1 if summary["pairs_out"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
