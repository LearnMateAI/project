"""
JSON bridge for the backend: run one resource generation and print the result as JSON.

Mirrors ingest_bridge.py's role -- a machine-facing entry point alongside the
human-facing cli.py and full_program.py. Takes learnmate's own doc_id (already known
to the backend from Day 10's ingest) rather than a session, since generation only
needs to know which document to pull source text from.

Usage:
    venv/bin/python scripts/generate_bridge.py <task> --doc <doc_id> [--count N] [--topic ...]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learnmate.ingestion import build_source_text
from learnmate.resource_agent import TASK_NAMES, generate_resource


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=TASK_NAMES)
    parser.add_argument("--doc", required=True, help="learnmate document id")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--topic", default=None)
    args = parser.parse_args()

    try:
        source = build_source_text(args.doc, topic=args.topic)
        result = generate_resource(
            args.task, source, count=args.count, doc_id=args.doc, verbose=False,
        )
        verdict = result.get("verdict") or {}
        print(json.dumps({
            "ok": True,
            "task": result["task"],
            "content": result["content"],
            "accepted": result["accepted"],
            "score": verdict.get("score"),
            "threshold": verdict.get("threshold"),
            "reasoning": verdict.get("reasoning"),
            "resource_id": result["resource_id"],
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
