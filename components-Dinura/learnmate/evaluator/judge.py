"""
The LLM judge.

Scores one piece of generated content from 1-100 against a rubric and says what to fix.
The verdict is grammar-constrained JSON, so the model cannot answer with prose about how
it would grade if it were grading.

Everything here fails closed. A judge that cannot be parsed, cannot be reached, or
answers with something unusable returns a failing verdict rather than an exception --
the caller is mid-loop and needs a decision, and silently passing unreviewed content
through is the one outcome worth ruling out. The reason always travels in `reasoning`,
so a failure stays visible instead of looking like a bad score.
"""

import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_judge_llm, parse_json_reply
from . import rubrics

# Constrained decoding: llama.cpp compiles this into a grammar, so the model cannot emit
# prose around the JSON or invent extra keys.
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 100},
        "reasoning": {"type": "string"},
        "regeneration_instruction": {"type": "string"},
    },
    "required": ["score", "reasoning", "regeneration_instruction"],
}

SYSTEM_PROMPT = """You are a strict evaluation model. You grade content produced by another AI.

Rules:
- Score from 1 to 100. Be harsh: 90+ means flawless, 70-89 usable with minor faults, 50-69 clearly weak, below 50 unusable.
- Judge only against the criteria and the material given. Never use outside knowledge to fill gaps.
- If the material is factually unsupported by the source, the score must be below 50.
- "reasoning" is at most 3 short sentences naming the concrete faults you found.
- "regeneration_instruction" is a direct order to the generator model telling it exactly what to fix and keep. Write one complete sentence of at least ten words that names the specific fault and the specific correction. Begin with an imperative verb such as Remove, Rewrite, Add or Replace, but never emit a bare verb or trailing dots: "Rewrite..." is not an instruction and will be rejected. Never write the corrected content itself, and never state a fact that is not in the material you were given: you are instructing a rewrite, not performing it. Write it even when the score is high; it is discarded when the score passes the threshold.
- Reply with JSON only."""

# A bare verb, optionally trailing dots: the judge echoing the prompt's example rather
# than writing an order. Anything this matches carries no information for the generator.
_BARE_VERB = re.compile(r"^(remove|rewrite|add|replace|revise|correct|fix)?[\s.…]*$",
                        re.IGNORECASE)

# Shorter than this and an "instruction" cannot name both a fault and a correction.
_MIN_INSTRUCTION_CHARS = 20


def _usable_instruction(instruction: str, reasoning: str) -> str:
    """
    Guarantee the retry loop has something to act on.

    A 3B judge intermittently answers with the example verb from the system prompt
    ("Rewrite...") instead of an actual order. Regenerating on that is strictly worse than
    not regenerating: the generator gets no signal and tends to collapse into a vaguer
    answer. The reasoning field does describe the fault, so fall back to it.
    """
    instruction = (instruction or "").strip()
    if len(instruction) >= _MIN_INSTRUCTION_CHARS and not _BARE_VERB.match(instruction):
        return instruction

    reasoning = (reasoning or "").strip()
    if reasoning:
        return f"Fix exactly this problem and change nothing else: {reasoning}"
    return "Regenerate the content; the evaluator returned no usable instruction."


def _failed_verdict(task: str, threshold: int, reasoning: str, instruction: str) -> Dict:
    return {
        "task": task,
        "score": 1,
        "passed": False,
        "reasoning": reasoning,
        "regeneration_instruction": instruction,
        "threshold": threshold,
    }


def parse_verdict(raw: Any) -> Dict:
    """Turn the model's reply into a verdict dict, tolerating stray prose or code fences."""
    try:
        data = parse_json_reply(raw)
    except ValueError:
        data = None

    if not isinstance(data, dict):
        text = raw if isinstance(raw, str) else str(raw)
        return {
            "score": 1,
            "reasoning": f"Could not parse evaluator output: {text.strip()[:200]}",
            "regeneration_instruction": "Regenerate the content; the evaluator returned "
                                        "an unreadable verdict.",
        }

    try:
        score = int(float(data.get("score", 1)))
    except (TypeError, ValueError):
        score = 1

    reasoning = str(data.get("reasoning", "")).strip()

    return {
        "score": max(1, min(100, score)),
        "reasoning": reasoning,
        "regeneration_instruction": _usable_instruction(
            str(data.get("regeneration_instruction", "")), reasoning),
    }


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

        parts = [f"Evaluation task: {task}", f"Criteria:\n{criteria}"]
        if source:
            parts.append(f'SOURCE MATERIAL:\n"""\n{source}\n"""')
        parts.append(f'CONTENT TO EVALUATE:\n"""\n{generated}\n"""')
        parts.append('Return JSON with exactly these keys: "score" (integer 1-100), '
                     '"reasoning" (string), "regeneration_instruction" (string).')

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="\n\n".join(parts)),
        ]

        try:
            reply = self.llm.invoke(messages, response_schema=VERDICT_SCHEMA)
            verdict = parse_verdict(reply.content)
        except Exception as exc:
            # Context overflow, OOM, a bad model file, an unreachable endpoint.
            return _failed_verdict(
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
            return _failed_verdict(
                "chat_msg", threshold,
                "The chat agent returned an empty reply.",
                "Regenerate the reply; the previous attempt produced no answer.",
            )

        blocks = []
        if history:
            lines = [f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '')}"
                     for turn in history]
            blocks.append("CONVERSATION SO FAR:\n" + "\n".join(lines))

        if contexts:
            chunks = [f"Page {getattr(c, 'metadata', {}).get('page_number', 'N/A')}: "
                      f"{getattr(c, 'page_content', c)}" for c in contexts]
            blocks.append("RETRIEVED CONTEXT (the reply may not go beyond this):\n"
                          + "\n\n".join(chunks))

        blocks.append(f"USER MESSAGE THE REPLY MUST ANSWER:\n{query}")

        return self.judge("chat_msg", reply, source="\n\n".join(blocks),
                          threshold=threshold, grounded=bool(contexts))


_JUDGE: Optional[Judge] = None


def get_judge() -> Judge:
    """Process-wide judge."""
    global _JUDGE
    if _JUDGE is None:
        _JUDGE = Judge()
    return _JUDGE
