"""
In-process per-user enqueue budget (F-07).

The worker is one thread. Without a cap, one account can fill the queue with ingest
and whole-document jobs and stall everyone else. This is not SlowAPI: it lives next
to enqueue so the job worker and the HTTP layer share one rule.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from learnmate import config as engine_config

from ..errors import RateLimited

_HITS = defaultdict(deque)
_LOCK = Lock()

_LIMITS = {
    "chat": lambda: engine_config.RATE_LIMIT_CHAT,
    "resource": lambda: engine_config.RATE_LIMIT_RESOURCE,
    "ingest": lambda: engine_config.RATE_LIMIT_INGEST,
}


def check_rate_limit(user_id: str, kind: str) -> None:
    """Raise RateLimited when this user has hit the rolling window for `kind`."""
    limit = _LIMITS.get(kind)
    if limit is None:
        return
    cap = limit()
    if cap <= 0:
        return

    window = engine_config.RATE_LIMIT_WINDOW_S
    key = (str(user_id), kind)
    now = time.monotonic()
    with _LOCK:
        bucket = _HITS[key]
        cutoff = now - window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= cap:
            retry = max(1, int(window - (now - bucket[0])) + 1)
            raise RateLimited(
                f"Too many {kind} requests. Try again in {retry} seconds.",
                retry_after=retry,
            )
        bucket.append(now)
