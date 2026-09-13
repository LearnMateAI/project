"""
Cooperative job deadline and stage clocks.

`LEARNMATE_JOB_TIMEOUT_S` is checked between graph nodes, not mid-token. llama.cpp
cannot be aborted cleanly, and a second thread calling it would interleave tokens with
the worker -- the same reason there is only one worker. A timed-out job therefore
finishes the inference already in flight, then the next node raises `JobTimeout`.
"""

from __future__ import annotations

import contextvars
import time
from typing import Dict, Optional

_deadline: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar(
    "learnmate_job_deadline", default=None,
)


class JobTimeout(TimeoutError):
    """The worker crossed LEARNMATE_JOB_TIMEOUT_S between stages."""


def set_deadline_seconds(seconds: int) -> None:
    """Arm a monotonic deadline for this worker thread, or clear it when seconds <= 0."""
    if seconds and seconds > 0:
        _deadline.set(time.monotonic() + float(seconds))
    else:
        _deadline.set(None)


def clear_deadline() -> None:
    _deadline.set(None)


def check_job_deadline() -> None:
    deadline = _deadline.get()
    if deadline is not None and time.monotonic() > deadline:
        raise JobTimeout(
            "This job exceeded LEARNMATE_JOB_TIMEOUT_S and was stopped between stages."
        )


def add_timing(state: Dict, key: str, started: float) -> Dict[str, int]:
    """Accumulate elapsed milliseconds onto `state['timings']` and return the new dict."""
    timings = dict(state.get("timings") or {})
    ms = int((time.perf_counter() - started) * 1000)
    timings[key] = timings.get(key, 0) + max(ms, 0)
    return timings
