"""Live Judge. This folder is a generator; the judge stays llama32-3b."""

PAIR_JUDGE = 'llama32-3b'

from learnmate.evaluator.judge import Judge, get_judge

__all__ = ["Judge", "get_judge", "PAIR_JUDGE"]
