"""
Whether the judge is worth running on this turn at all.

The judge is the most expensive thing in a chat turn -- a second 3B model reading the
question, the retrieved chunks and the reply, and on the local backend that measured a
median of 36 seconds against a generation of roughly fifteen. Paying it is worth it when
the verdict decides something. This module is the check for whether it does.

The rule is decided by retrieval mode, because that is what determines whether the judge
has anything to check the reply *against*:

    pdf mode      the reply was written from retrieved chunks, and the grounded rubric
                  holds it to them: any claim beyond the context is a hallucination and
                  scores below 50. The judge discriminates here -- across this project's
                  logged verdicts, pdf-mode scores run the full range and about two thirds
                  are rejected. This is the gate doing its job, and it is not skipped.

    general mode  nothing relevant was retrieved, so there is no source text. The rubric
                  can only ask about relevance, coherence and informativeness, and a 3B
                  judge asked that with no material to compare against returns the same
                  number every time -- every general-mode verdict logged here is exactly
                  100. A score with no variance separates nothing at any threshold.

So the default skips general mode and keeps pdf mode. That is the opposite of the obvious
guess, which is that a grounded answer is the safe one to wave through: grounded answers
are the ones this judge actually catches.

What a skip is not: it is not `evaluate=False`. That switch turns the whole gate off and is
for callers wanting raw speed. This one is per-turn and recorded -- a skipped turn is
written to the evaluation log with stage="gate", so the decision stays auditable and the
statistics do not quietly become a survey of pdf-mode turns only.
"""

from typing import Optional

from .. import config
from .state import ChatState


def skip_reason(state: ChatState) -> Optional[str]:
    """
    Why the judge should be skipped for this turn, or None to run it.

    The returned string is recorded as the verdict's `reasoning` and surfaces in the API
    response, so it is written to be read by whoever is wondering where the score went.
    """
    if not config.JUDGE_GATE_MODES:
        return None

    mode = (state.get("mode") or "").lower()
    # An unknown or missing mode judges, rather than skipping on a value nobody set.
    if mode not in config.JUDGE_GATE_MODES:
        return None

    # An empty reply is a failed generation, and the judge fails it in microseconds without
    # calling a model -- see judge.judge_chat_reply. That is a real verdict worth having,
    # and it is what lets the retry loop recover, so it is never gated away.
    if not (state.get("reply") or "").strip():
        return None

    return (
        f"Not scored: this reply was answered from general knowledge, so there is no "
        f"retrieved source text to check it against. The evaluator was skipped rather "
        f"than asked for a number it cannot ground (mode={mode})."
    )
