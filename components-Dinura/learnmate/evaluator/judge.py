"""
Gate 2: the LLM judge.

Scores one piece of generated content from 1-100 against a rubric and says what to fix.
The verdict is grammar-constrained JSON, so the model cannot answer with prose about how
it would grade if it were grading.

Two entry points, one per producer in this system:

    judge()             a generated resource, graded against the PDF passage it came from
                        -- called by resource_agent/graph.py's check node
    judge_chat_reply()  one chat turn, graded against the retrieved chunks if there were
                        any -- called by chat_agent/evaluate.py

The second is a thin wrapper over the first. What differs is only how the "source
material" is assembled and which rubric applies, and both of those decisions are made
here rather than by the caller.

This file is orchestration only. The prompt is in prompt.py, the criteria in rubrics.py,
the parsing and the fail-closed verdicts in verdict.py.
"""

from typing import Dict, List, Optional

from .. import config
from ..llm import get_judge_llm
from . import prompt, rubrics
from .verdict import VERDICT_SCHEMA, failed_verdict, parse_verdict


class Judge:
    """Grades generated content against a rubric."""

    def __init__(self, llm=None, threshold: int = None):
        self._llm = llm
        self.threshold = threshold if threshold is not None else config.EVALUATOR_THRESHOLD

    @property
    def llm(self):
        # Lazy so constructing a Judge does not load 2 GB of weights; the resource graph
        # builds one even when evaluation is switched off.
        if self._llm is None:
            self._llm = get_judge_llm()
        return self._llm

    def judge(self, task: str, generated: str, source: str = None, criteria: str = None,
              threshold: int = None, grounded: bool = False) -> Dict:
        """
        Score one artefact and say how to regenerate it.

        task      -- "mcq", "summary", "chat_msg", ...; selects the default rubric
        generated -- the content being graded, as text
        source    -- the material it must be faithful to; optional
        criteria  -- overrides the default rubric for the task
        grounded  -- for chat, whether retrieved context applies (selects the strict rubric)

        Returns {task, score, passed, reasoning, regeneration_instruction, threshold}.
        `regeneration_instruction` is emptied when the score passes, so callers can check
        either `passed` or the instruction's truthiness.
        """
        threshold = threshold if threshold is not None else self.threshold
        criteria = criteria or rubrics.for_task(task, grounded=grounded)

        messages = prompt.build_messages(task, generated, criteria, source=source)

        try:
            reply = self.llm.invoke(messages, response_schema=VERDICT_SCHEMA)
            verdict = parse_verdict(reply.content)
        except Exception as exc:
            # Context overflow, OOM, a bad model file, an unreachable endpoint. Fail
            # closed: a failing verdict, never an exception into the caller's loop.
            return failed_verdict(
                task, threshold,
                f"Evaluator could not run: {type(exc).__name__}: {exc}",
                "Regenerate the content; the evaluator failed to return a verdict.",
            )

        verdict["task"] = task
        verdict["threshold"] = threshold
        verdict["passed"] = verdict["score"] >= threshold
        if verdict["passed"]:
            verdict["regeneration_instruction"] = ""
        return verdict

    # --- Chat-specific entry point ---------------------------------------------------

    def judge_chat_reply(self, query: str, reply: str, contexts: Optional[List] = None,
                         history: Optional[List[Dict]] = None,
                         threshold: int = None) -> Dict:
        """
        Score one chat turn.

        Passing `contexts` is what selects the strict grounded rubric: the reply is then
        held to the retrieved chunks and anything beyond them is a hallucination. Without
        contexts the reply came from general knowledge and there is nothing to check it
        against, so only relevance, coherence and informativeness are judged.
        """
        threshold = threshold if threshold is not None else self.threshold
        reply = (reply or "").strip()

        # Don't burn ~25s of CPU judging an empty reply; it is a failure by definition.
        if not reply:
            return failed_verdict(
                "chat_msg", threshold,
                "The chat agent returned an empty reply.",
                "Regenerate the reply; the previous attempt produced no answer.",
            )

        source = prompt.build_chat_source(query, contexts=contexts, history=history)
        return self.judge("chat_msg", reply, source=source, threshold=threshold,
                          grounded=bool(contexts))


_JUDGE: Optional[Judge] = None


def get_judge() -> Judge:
    """Process-wide judge."""
    global _JUDGE
    if _JUDGE is None:
        _JUDGE = Judge()
    return _JUDGE
