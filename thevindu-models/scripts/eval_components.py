"""
Swap each comparison model into the LIVE chat_agent / evaluator without editing .env.

Generators: learnmate.chat_agent.generate.generate_node(model_id=...)
MCQ: live resource_agent MCQ prompt + schema + Gate 1 validators
Judges: learnmate.evaluator.Judge(llm=candidate) — real SystemMessage rubric

Does not write Qdrant or Mongo. Does not flip selectable_default.
Never loads the same family as generator and judge in one process.
"""

from __future__ import annotations

import argparse
import json
import platform
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

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from learnmate.llm import parse_json_reply
from learnmate.llm.llamacpp import LlamaCppChatModel
from learnmate.llm.runtime import unload_llama
from learnmate.resource_agent.mcq import MCQ, build_prompt, resolve_difficulty


def _gguf_path(entry: Dict):
    path = models_dir() / entry["gguf_path"]
    return path if path.is_file() else None


def _family(entry: Dict) -> str:
    raw = (entry.get("incompatible_generator_families") or "").strip().lower()
    if raw:
        return raw.split(",")[0].strip()
    token = (entry.get("id") or "").lower()
    for name in ("qwen", "gemma", "phi", "llama", "granite"):
        if name in token:
            return name
    return token


def _assert_pairing(judges: List[Dict], gens: List[Dict]) -> None:
    gen_families = {_family(g) for g in gens}
    same = [j for j in judges if _family(j) in gen_families]
    if same:
        names = ", ".join(j["id"] for j in same)
        raise SystemExit(
            f"Refusing same-family generator+judge in one process: {names}."
        )


def eval_generator(entry: Dict, prompts: List[Dict]) -> Dict:
    path = _gguf_path(entry)
    if path is None:
        return {"id": entry["id"], "skipped": True, "reason": "gguf_missing",
                "expected": str(models_dir() / entry["gguf_path"])}

    from learnmate.chat_agent.generate import generate_node
    from learnmate.evaluator.validators import validate

    rows = []
    model_id = entry["id"]
    for item in prompts:
        started = time.perf_counter()
        if item["kind"] == "qa":
            state = {
                "query": item["question"],
                "contexts": [Document(
                    page_content=item["passage"],
                    metadata={"page_number": 1},
                )],
                "attempt": 0,
                "max_attempts": 1,
                "evaluate": False,
                "verbose": False,
                "history": [],
                "threshold": 70,
                "model_id": model_id,
                "timings": {},
            }
            try:
                out = generate_node(state)
                text = (out.get("reply") or "").strip()
            except Exception as exc:
                text = ""
                rows.append({
                    "id": item["id"], "kind": "qa",
                    "ms": round((time.perf_counter() - started) * 1000),
                    "must_contain_hits": 0,
                    "must_contain_n": len(item.get("must_contain") or []),
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                    "preview": "",
                })
                print(f"    {entry['id']} {item['id']}: FAIL {rows[-1]['error']}")
                continue
            elapsed = time.perf_counter() - started
            lowered = text.lower()
            hits = [tok for tok in item.get("must_contain") or [] if tok.lower() in lowered]
            rows.append({
                "id": item["id"], "kind": "qa",
                "ms": round(elapsed * 1000),
                "must_contain_hits": len(hits),
                "must_contain_n": len(item.get("must_contain") or []),
                "preview": text[:240],
            })
        else:
            llm = None
            try:
                from learnmate.llm.registry import get_generator_llm
                llm = get_generator_llm(model_id=model_id, temperature=0.3, max_tokens=256)
                messages = [
                    SystemMessage(content=MCQ.system_prompt),
                    HumanMessage(content=build_prompt(item["passage"], 1, "medium")),
                ]
                reply = llm.invoke(messages, response_schema=MCQ.schema)
                text = reply.content or ""
                content = MCQ.unwrap(parse_json_reply(text))
                if isinstance(content, list):
                    tier = resolve_difficulty("medium")
                    for q in content:
                        if isinstance(q, dict):
                            q.setdefault("difficulty", tier)
                ok, reasons = validate("mcq", content)
            except Exception as exc:
                text = ""
                ok, reasons = False, [f"{type(exc).__name__}: {exc}"]
            elapsed = time.perf_counter() - started
            rows.append({
                "id": item["id"], "kind": "mcq_json",
                "ms": round(elapsed * 1000),
                "json_valid": bool(ok),
                "parse_error": "; ".join(reasons) if reasons else "",
                "preview": (text or "")[:240],
            })
        print(f"    {entry['id']} {item['id']}: {rows[-1]}")

    unload_llama(str(path))
    qa = [r for r in rows if r["kind"] == "qa"]
    mcq = [r for r in rows if r["kind"] == "mcq_json"]
    return {
        "id": entry["id"],
        "skipped": False,
        "component": "integrated-backend/learnmate/chat_agent/generate.py + resource_agent/mcq.py",
        "display_name": entry.get("display_name"),
        "grounded_hit_rate": round(
            sum(r["must_contain_hits"] / max(r["must_contain_n"], 1) for r in qa) / len(qa), 4
        ) if qa else None,
        "json_valid_rate": round(sum(1 for r in mcq if r["json_valid"]) / len(mcq), 4) if mcq else None,
        "mean_ms": round(sum(r["ms"] for r in rows) / len(rows), 1) if rows else None,
        "items": rows,
    }


def eval_judge(entry: Dict, cases: List[Dict]) -> Dict:
    path = _gguf_path(entry)
    if path is None:
        return {"id": entry["id"], "skipped": True, "reason": "gguf_missing",
                "expected": str(models_dir() / entry["gguf_path"])}

    from learnmate.evaluator.judge import Judge

    llm = LlamaCppChatModel(
        gguf_path=str(path),
        n_ctx=int(entry.get("context_length") or 8192),
        chat_format=None,
        temperature=0.0,
        max_tokens=512,
    )
    judge = Judge(llm=llm, threshold=70)
    system_ok = True
    rows = []
    for item in cases:
        started = time.perf_counter()
        contexts = [Document(page_content=item["passage"], metadata={"page_number": 1})]
        try:
            verdict = judge.judge_chat_reply(
                "Is the following claim supported by the retrieved context?",
                item["claim"],
                contexts=contexts,
                threshold=70,
            )
        except ValueError as exc:
            if "system" not in str(exc).lower():
                raise
            system_ok = False
            verdict = {
                "score": 0,
                "passed": False,
                "reasoning": f"SystemMessage rejected: {exc}",
                "regeneration_instruction": "",
            }
        elapsed = time.perf_counter() - started
        score = verdict.get("score")
        predicted_pass = bool(verdict.get("passed"))
        gold = bool(item["gold_pass"])
        rows.append({
            "id": item["id"],
            "ms": round(elapsed * 1000),
            "gold_pass": gold,
            "predicted_pass": predicted_pass,
            "score": score,
            "correct": predicted_pass == gold,
            "preview": (verdict.get("reasoning") or "")[:240],
        })
        print(f"    {entry['id']} {item['id']}: gold={gold} pred={predicted_pass} score={score}")

    unload_llama(str(path))
    n = len(rows) or 1
    return {
        "id": entry["id"],
        "skipped": False,
        "component": "integrated-backend/learnmate/evaluator/judge.py",
        "display_name": entry.get("display_name"),
        "accuracy": round(sum(1 for r in rows if r["correct"]) / n, 4),
        "mean_ms": round(sum(r["ms"] for r in rows) / len(rows), 1),
        "system_role_supported": system_ok,
        "items": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generators", nargs="*", default=None)
    parser.add_argument("--judges", nargs="*", default=None)
    args = parser.parse_args()

    registry = load_comparison_registry()
    gens = list(registry["generators"])
    judges = list(registry["judges"])
    if args.generators is not None:
        gens = [g for g in gens if g["id"] in set(args.generators)]
        judges = [] if args.judges is None else [j for j in judges if j["id"] in set(args.judges)]
    if args.judges is not None and args.generators is None:
        gens = []
        judges = [j for j in judges if j["id"] in set(args.judges)]
    if args.generators is None and args.judges is None:
        # Sequential roles in one process would load both. Run generators first;
        # judges must be a second invocation (same as eval_gguf.py pairing rule).
        judges = []

    _assert_pairing(judges, gens)

    prompts = load_jsonl(FIXTURES_DIR / "generator_prompts.jsonl")
    cases = load_jsonl(FIXTURES_DIR / "judge_gold.jsonl")
    machine = {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "note": "Laptop CPU; live chat_agent/evaluator components; not Colab, not uvicorn p95.",
    }

    gen_reports = []
    for entry in gens:
        print(f"[*] Component generator {entry['id']}")
        try:
            gen_reports.append(eval_generator(entry, prompts))
        except Exception as exc:
            print(f"[!] {entry['id']} failed: {type(exc).__name__}: {exc}")
            try:
                path = _gguf_path(entry)
                if path:
                    unload_llama(str(path))
            except Exception:
                pass
            gen_reports.append({
                "id": entry["id"], "skipped": True, "reason": "eval_failed",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            })

    judge_reports = []
    for entry in judges:
        print(f"[*] Component judge {entry['id']}")
        try:
            judge_reports.append(eval_judge(entry, cases))
        except Exception as exc:
            print(f"[!] {entry['id']} failed: {type(exc).__name__}: {exc}")
            try:
                path = _gguf_path(entry)
                if path:
                    unload_llama(str(path))
            except Exception:
                pass
            judge_reports.append({
                "id": entry["id"], "skipped": True, "reason": "eval_failed",
                "error": f"{type(exc).__name__}: {exc}"[:500],
            })

    out = RESULTS_DIR / "components.json"
    payload = {}
    if out.is_file():
        try:
            payload = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    by_g = {r.get("id"): r for r in payload.get("generators") or [] if r.get("id")}
    by_j = {r.get("id"): r for r in payload.get("judges") or [] if r.get("id")}
    for row in gen_reports:
        by_g[row["id"]] = row
    for row in judge_reports:
        by_j[row["id"]] = row
    payload = {
        "path": "live integrated-backend chat_agent + evaluator (same as components-Dinura)",
        "env_changed": False,
        "selectable_default_changed": False,
        "machine": machine,
        "generators": list(by_g.values()),
        "judges": list(by_j.values()),
    }
    write_json(out, payload)
    print(f"[*] Wrote {out}")
    print(json.dumps({
        "generators": [
            {k: r.get(k) for k in (
                "id", "skipped", "grounded_hit_rate", "json_valid_rate", "mean_ms", "error")}
            for r in payload["generators"]
        ],
        "judges": [
            {k: r.get(k) for k in (
                "id", "skipped", "accuracy", "mean_ms", "system_role_supported", "error")}
            for r in payload["judges"]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
