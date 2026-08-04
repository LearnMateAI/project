"""
Append-only log of every evaluation, for calibrating thresholds later.

A threshold picked before seeing the score distribution is a guess. Observed so far: the
Llama 3.2 3B judge scored two near-identical chat replies 1 and 90, so a single reading of
its score is not yet trustworthy as a gate. Logging every verdict is what turns that from
an impression into something measurable.

One JSON object per line, so it can be read back with json.loads per line or loaded into
pandas without a parser.
"""

import json
import os
import time

DEFAULT_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.jsonl")


def log_evaluation(task: str, attempt: int, score, passed: bool, threshold: int,
                   stage: str = "judge", elapsed: float = None, extra: dict = None,
                   path: str = DEFAULT_LOG_PATH) -> None:
    """
    Record one verdict.

    stage -- "validator" when structural checks rejected the content without the judge
             running, "judge" when the LLM scored it. Keeping both makes it possible to
             ask how often the cheap gate is doing the work.

    Never raises: logging must not be able to take down a generation run.
    """
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "task": task,
        "attempt": attempt,
        "stage": stage,
        "score": score,
        "passed": bool(passed),
        "threshold": threshold,
    }
    if elapsed is not None:
        record["elapsed_s"] = round(elapsed, 2)
    if extra:
        record.update(extra)

    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_log(path: str = DEFAULT_LOG_PATH) -> list:
    """Load the log, skipping any line that is not valid JSON."""
    if not os.path.exists(path):
        return []

    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records


def summarise(path: str = DEFAULT_LOG_PATH) -> dict:
    """
    Score distribution per task, for deciding whether a threshold is meaningful.

    A judge whose scores cluster in a narrow band cannot separate good from bad at any
    threshold, however it is set.
    """
    records = [r for r in read_log(path) if r.get("stage") == "judge"
               and isinstance(r.get("score"), (int, float))]
    if not records:
        return {}

    out = {}
    tasks = {r["task"] for r in records}
    for task in sorted(tasks):
        scores = sorted(r["score"] for r in records if r["task"] == task)
        n = len(scores)
        out[task] = {
            "n": n,
            "min": scores[0],
            "median": scores[n // 2],
            "max": scores[-1],
            "distinct": len(set(scores)),
            "pass_rate": round(
                sum(1 for r in records if r["task"] == task and r["passed"]) / n, 3),
        }
    return out
