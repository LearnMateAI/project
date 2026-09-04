"""
Optional GGUF smoke for generator and judge candidates.

Skips any file that is not already on disk. Does not download ~2 GB weights unless you
pass --fetch. Never loads the same GGUF as generator and judge in one process.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Dict, List, Optional

from common import (
    FIXTURES_DIR,
    RESULTS_DIR,
    ensure_backend_on_path,
    load_comparison_registry,
    load_jsonl,
    models_dir,
    write_json,
)

ensure_backend_on_path()

from langchain_core.messages import HumanMessage, SystemMessage

from learnmate.llm.json_output import parse_json_reply
from learnmate.llm.llamacpp import LlamaCppChatModel
from learnmate.llm.runtime import unload_llama


MCQ_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "answer": {"type": "string"},
    },
    "required": ["question", "options", "answer"],
}

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 100},
        "reasoning": {"type": "string"},
        "regeneration_instruction": {"type": "string"},
    },
    "required": ["score", "reasoning", "regeneration_instruction"],
}


def _gguf_path(entry: Dict):
    path = models_dir() / entry["gguf_path"]
    return path if path.is_file() else None


def _chat(path, n_ctx: int, messages, max_tokens: int, temperature: float,
          schema: Optional[dict] = None) -> str:
    llm = LlamaCppChatModel(
        gguf_path=str(path),
        n_ctx=n_ctx,
        chat_format=None,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    kwargs = {"max_tokens": max_tokens, "temperature": temperature}
    if schema is not None:
        kwargs["response_schema"] = schema
    result = llm._generate(messages, **kwargs)
    return result.generations[0].message.content


def eval_generator(entry: Dict, prompts: List[Dict]) -> Dict:
    path = _gguf_path(entry)
    if path is None:
        return {"id": entry["id"], "skipped": True, "reason": "gguf_missing",
                "expected": str(models_dir() / entry["gguf_path"])}

    rows = []
    for item in prompts:
        started = time.perf_counter()
        if item["kind"] == "qa":
            text = _chat(
                path, int(entry.get("context_length") or 4096),
                [HumanMessage(content=(
                    "Answer using only the passage. If the passage does not say, say you "
                    "cannot tell.\n\nPassage:\n"
                    f"{item['passage']}\n\nQuestion: {item['question']}"
                ))],
                max_tokens=160, temperature=0.2,
            )
            elapsed = time.perf_counter() - started
            lowered = (text or "").lower()
            hits = [tok for tok in item.get("must_contain") or [] if tok.lower() in lowered]
            rows.append({
                "id": item["id"], "kind": "qa", "ms": round(elapsed * 1000),
                "must_contain_hits": len(hits),
                "must_contain_n": len(item.get("must_contain") or []),
                "preview": (text or "")[:240],
            })
        else:
            text = _chat(
                path, int(entry.get("context_length") or 4096),
                [HumanMessage(content=(
                    f"{item['instruction']}\n\nPassage:\n{item['passage']}"
                ))],
                max_tokens=256, temperature=0.3, schema=MCQ_SCHEMA,
            )
            elapsed = time.perf_counter() - started
            valid = False
            detail = ""
            try:
                parsed = parse_json_reply(text)
                valid = (
                    isinstance(parsed, dict)
                    and isinstance(parsed.get("options"), list)
                    and len(parsed.get("options") or []) == 4
                    and parsed.get("answer") in parsed.get("options")
                )
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
            rows.append({
                "id": item["id"], "kind": "mcq_json", "ms": round(elapsed * 1000),
                "json_valid": valid, "parse_error": detail,
                "preview": (text or "")[:240],
            })
        print(f"    {entry['id']} {item['id']}: {rows[-1]}")

    unload_llama(str(path))
    qa = [r for r in rows if r["kind"] == "qa"]
    mcq = [r for r in rows if r["kind"] == "mcq_json"]
    total_chars = sum(len(r.get("preview") or "") for r in rows)
    total_s = (sum(r["ms"] for r in rows) / 1000) if rows else 0
    return {
        "id": entry["id"],
        "skipped": False,
        "display_name": entry.get("display_name"),
        "grounded_hit_rate": round(
            sum(r["must_contain_hits"] / max(r["must_contain_n"], 1) for r in qa) / len(qa), 4
        ) if qa else None,
        "json_valid_rate": round(sum(1 for r in mcq if r["json_valid"]) / len(mcq), 4) if mcq else None,
        "mean_ms": round(sum(r["ms"] for r in rows) / len(rows), 1) if rows else None,
        "approx_chars_per_s": round(total_chars / total_s, 1) if total_s else None,
        "items": rows,
    }


def eval_judge(entry: Dict, cases: List[Dict]) -> Dict:
    path = _gguf_path(entry)
    if path is None:
        return {"id": entry["id"], "skipped": True, "reason": "gguf_missing",
                "expected": str(models_dir() / entry["gguf_path"])}

    rows = []
    system_ok = True
    system_text = (
        "You grade whether a claim is supported by the passage. "
        "score 1-100. passed means score >= 70. If the claim cites a source "
        "or rule that is not in the passage, fail it."
    )
    for item in cases:
        started = time.perf_counter()
        user_text = (
            f"Passage:\n{item['passage']}\n\nClaim:\n{item['claim']}\n\n"
            "Reply JSON with score, reasoning, regeneration_instruction."
        )
        try:
            text = _chat(
                path, int(entry.get("context_length") or 8192),
                [SystemMessage(content=system_text), HumanMessage(content=user_text)],
                max_tokens=220, temperature=0.0, schema=VERDICT_SCHEMA,
            )
        except ValueError as exc:
            if "system" not in str(exc).lower():
                raise
            system_ok = False
            text = _chat(
                path, int(entry.get("context_length") or 8192),
                [HumanMessage(content=system_text + "\n\n" + user_text)],
                max_tokens=220, temperature=0.0, schema=VERDICT_SCHEMA,
            )
        elapsed = time.perf_counter() - started
        parsed = None
        try:
            parsed = parse_json_reply(text)
        except Exception:
            parsed = None
        score = int(parsed["score"]) if isinstance(parsed, dict) and "score" in parsed else None
        predicted_pass = score is not None and score >= 70
        gold = bool(item["gold_pass"])
        rows.append({
            "id": item["id"],
            "ms": round(elapsed * 1000),
            "gold_pass": gold,
            "predicted_pass": predicted_pass,
            "score": score,
            "correct": predicted_pass == gold,
            "preview": (text or "")[:240],
        })
        print(f"    {entry['id']} {item['id']}: gold={gold} pred={predicted_pass} score={score}")

    unload_llama(str(path))
    n = len(rows) or 1
    return {
        "id": entry["id"],
        "skipped": False,
        "display_name": entry.get("display_name"),
        "accuracy": round(sum(1 for r in rows if r["correct"]) / n, 4),
        "mean_ms": round(sum(r["ms"] for r in rows) / len(rows), 1),
        "system_role_supported": system_ok,
        "items": rows,
    }


def _family(entry: Dict) -> str:
    raw = (entry.get("incompatible_generator_families") or "").strip().lower()
    if raw:
        return raw.split(",")[0].strip()
    token = (entry.get("id") or "").lower()
    for name in ("qwen", "gemma", "phi", "llama", "granite"):
        if name in token:
            return name
    return token


def _assert_pairing(judges: List[Dict], generator_under_test: Optional[str],
                    registry: Dict) -> None:
    """Refuse Gemma-judge + Gemma-generator (and any same-family pair)."""
    if not generator_under_test or not judges:
        return
    gen = next((g for g in registry["generators"] if g["id"] == generator_under_test), None)
    gen_family = _family(gen) if gen else _family({"id": generator_under_test})
    blocked = [j for j in judges if _family(j) == gen_family]
    if blocked:
        names = ", ".join(j["id"] for j in blocked)
        raise SystemExit(
            f"Refusing same-family pairing: generator {generator_under_test!r} "
            f"(family {gen_family}) with judge(s) {names}. "
            "That is the failure mode Llama-3.2 exists to prevent."
        )


def _merge_reports(path, payload: Dict) -> Dict:
    """Keep earlier generator/judge rows when this process only scored one role."""
    if not path.is_file():
        return payload
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return payload
    merged = dict(previous)
    for role in ("generators", "judges"):
        by_id = {row.get("id"): row for row in previous.get(role) or [] if row.get("id")}
        for row in payload.get(role) or []:
            by_id[row["id"]] = row
        merged[role] = list(by_id.values())
    merged["pairing_rule"] = payload.get("pairing_rule") or previous.get("pairing_rule")
    merged["machine"] = payload.get("machine") or previous.get("machine")
    merged["generator_under_test"] = payload.get("generator_under_test") or previous.get(
        "generator_under_test"
    )
    return merged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true",
                        help="Download missing GGUFs named on the command line")
    parser.add_argument("--generators", nargs="*", default=None)
    parser.add_argument("--judges", nargs="*", default=None)
    parser.add_argument(
        "--generator-under-test",
        default=None,
        help="Family check: refuse a judge that shares this generator's family.",
    )
    args = parser.parse_args()

    registry = load_comparison_registry()
    gens = registry["generators"]
    judges = registry["judges"]
    run_gens = args.generators is not None or args.judges is None
    run_judges = args.judges is not None or args.generators is None
    if args.generators is not None:
        gens = [g for g in gens if g["id"] in set(args.generators)]
    else:
        gens = gens if run_gens else []
    if args.judges is not None:
        judges = [j for j in judges if j["id"] in set(args.judges)]
    else:
        judges = judges if run_judges else []

    _assert_pairing(judges, args.generator_under_test, registry)
    # Same-process guard even when --generator-under-test is omitted.
    gen_families = {_family(g) for g in gens}
    same = [j for j in judges if _family(j) in gen_families]
    if same:
        names = ", ".join(j["id"] for j in same)
        raise SystemExit(
            f"Refusing to load the same family as generator and judge in one process: {names}."
        )

    if args.fetch:
        from learnmate.llm.download import ensure_gguf
        for entry in gens + judges:
            dest = models_dir() / entry["gguf_path"]
            if not dest.is_file():
                ensure_gguf(str(dest), entry.get("hf_repo") or "", entry.get("hf_file") or "")

    prompts = load_jsonl(FIXTURES_DIR / "generator_prompts.jsonl")
    cases = load_jsonl(FIXTURES_DIR / "judge_gold.jsonl")

    import platform
    machine = {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "note": "Laptop CPU GGUF eval; not Colab T4, not a production GPU box.",
    }

    gen_reports = []
    for entry in gens:
        print(f"[*] Generator {entry['id']}")
        try:
            gen_reports.append(eval_generator(entry, prompts))
        except Exception as exc:
            print(f"[!] Generator {entry['id']} failed: {type(exc).__name__}: {exc}")
            try:
                path = _gguf_path(entry)
                if path:
                    unload_llama(str(path))
            except Exception:
                pass
            gen_reports.append({
                "id": entry["id"], "skipped": True,
                "reason": "eval_failed",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            })

    judge_reports = []
    for entry in judges:
        print(f"[*] Judge {entry['id']}")
        try:
            judge_reports.append(eval_judge(entry, cases))
        except Exception as exc:
            print(f"[!] Judge {entry['id']} failed: {type(exc).__name__}: {exc}")
            try:
                path = _gguf_path(entry)
                if path:
                    unload_llama(str(path))
            except Exception:
                pass
            judge_reports.append({
                "id": entry["id"], "skipped": True,
                "reason": "eval_failed",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            })

    payload = {
        "generators": gen_reports,
        "judges": judge_reports,
        "generator_under_test": args.generator_under_test,
        "machine": machine,
        "pairing_rule": (
            "Never score a judge that shares a family with the generator under test. "
            "Gemma-as-judge is only valid next to Qwen or Phi. Granite-as-judge is valid "
            "next to Qwen, Phi, or Gemma."
        ),
    }
    out = RESULTS_DIR / "gguf.json"
    payload = _merge_reports(out, payload)
    write_json(out, payload)
    print(f"[*] Wrote {out}")
    print(json.dumps({
        "machine": machine,
        "generators": [
            {k: r.get(k) for k in (
                "id", "skipped", "reason", "grounded_hit_rate", "json_valid_rate",
                "mean_ms", "error")}
            for r in payload.get("generators") or []
        ],
        "judges": [
            {k: r.get(k) for k in (
                "id", "skipped", "reason", "accuracy", "mean_ms", "error")}
            for r in payload.get("judges") or []
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
