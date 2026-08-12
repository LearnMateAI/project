"""
Subprocess bridge into components-Dinura's local model pipeline.
"""

import json
import os
import subprocess

LEARNMATE_PYTHON = os.environ.get("LEARNMATE_PYTHON", "../components-Dinura/venv/bin/python")
LEARNMATE_SCRIPTS_DIR = os.environ.get("LEARNMATE_SCRIPTS_DIR", "../components-Dinura/scripts")

INGEST_TIMEOUT_S = 300


def run_ingest(pdf_path: str, session_id: str) -> dict:
    """
    Run one PDF through learnmate's ingest pipeline and return its report.

    Raises RuntimeError with a human-readable message on any failure, so the caller's
    except block has something meaningful to store in processing_error.
    """
    script = os.path.join(LEARNMATE_SCRIPTS_DIR, "ingest_bridge.py")
    result = subprocess.run(
        [LEARNMATE_PYTHON, script, pdf_path, "--session", session_id, "--for", "both"],
        capture_output=True, text=True, timeout=INGEST_TIMEOUT_S,
    )

    # Take the LAST line of stdout, not the whole thing: a first-run model load can
    # print warnings/progress noise before the JSON line we actually want.
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(
            f"learnmate ingest produced no parseable output. "
            f"stderr: {result.stderr[-500:]}"
        )

    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", "unknown learnmate ingest failure"))

    return payload


# Judge grading can trigger up to one retry per task, so this is more generous than
# ingest's timeout -- worst case is two full generation passes plus two judge calls.
GENERATE_TIMEOUT_S = 600


def run_generate(task: str, doc_id: str, count: int = 5) -> dict:
    """
    Run one resource generation through learnmate and return its result.

    Same fail-closed contract as run_ingest: raises RuntimeError with a readable message
    on any failure, so the caller has something to store in the resource's error field.
    """
    script = os.path.join(LEARNMATE_SCRIPTS_DIR, "generate_bridge.py")
    result = subprocess.run(
        [LEARNMATE_PYTHON, script, task, "--doc", doc_id, "--count", str(count)],
        capture_output=True, text=True, timeout=GENERATE_TIMEOUT_S,
    )

    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(
            f"learnmate generate produced no parseable output. "
            f"stderr: {result.stderr[-500:]}"
        )

    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", "unknown learnmate generate failure"))

    return payload
