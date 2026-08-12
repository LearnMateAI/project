"""
JSON bridge for the backend: run one ingest and print the result as JSON.

Not part of cli.py or full_program.py -- those are human-facing (interactive prompts,
formatted tables). This is a third, minimal entry point for another process (the
LearnMateAI FastAPI backend) to call learnmate.ingest_pdf() and get one machine-readable
line back, with a predictable {ok, ...} shape on both success and failure.

Usage:
    venv/bin/python scripts/ingest_bridge.py <pdf_path> --session <id> [--for chat|resource|both]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learnmate import ingest_pdf  # noqa: E402  (import after sys.path fix, same pattern as cli.py)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="path to the PDF on disk")
    parser.add_argument("--session", required=True, help="session id to bind this PDF to")
    parser.add_argument("--for", dest="session_for", default="both",
                        choices=["chat", "resource", "both"])
    args = parser.parse_args()

    try:
        report = ingest_pdf(args.path, session_id=args.session,
                            session_for=args.session_for, verbose=False)
        print(json.dumps({
            "ok": True,
            "doc_id": report["doc_id"],
            "n_pages": report["n_pages"],
            "n_chunks": report["n_chunks"],
            "skipped": report["skipped"],
        }))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
