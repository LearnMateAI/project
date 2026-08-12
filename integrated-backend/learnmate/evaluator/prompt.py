"""
What the judge is actually shown.

Two pieces: the system prompt that sets the grading behaviour, and the assembly of one
user message out of the rubric, the source material and the content being graded.

The scoring bands and the "below 50" instruction matter more than they look. A 3B model
told "rate the quality" returns 75 for everything, and a grade that never varies cannot
gate anything -- so the prompt names what should push a score down, and the rubrics
(rubrics.py) name it again per task.
"""

from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

SYSTEM_PROMPT = """You are a strict evaluation model. You grade content produced by another AI.

Rules:
- Score from 1 to 100. Be harsh: 90+ means flawless, 70-89 usable with minor faults, 50-69 clearly weak, below 50 unusable.
- Judge only against the criteria and the material given. Never use outside knowledge to fill gaps.
- If the material is factually unsupported by the source, the score must be below 50.
- "reasoning" is at most 3 short sentences naming the concrete faults you found.
- "regeneration_instruction" is a direct order to the generator model telling it exactly what to fix and keep. Write one complete sentence of at least ten words that names the specific fault and the specific correction. Begin with an imperative verb such as Remove, Rewrite, Add or Replace, but never emit a bare verb or trailing dots: "Rewrite..." is not an instruction and will be rejected. Never write the corrected content itself, and never state a fact that is not in the material you were given: you are instructing a rewrite, not performing it. Write it even when the score is high; it is discarded when the score passes the threshold.
- Reply with JSON only."""


def build_messages(task: str, generated: str, criteria: str,
                   source: Optional[str] = None) -> List:
    """
    Assemble the judge's prompt.

    Order matters: criteria first so the model knows what it is looking for, then the
    source it must check against, then the content itself, then the output contract. A
    model shown the content before the criteria starts forming an opinion first.
    """
    parts = [f"Evaluation task: {task}", f"Criteria:\n{criteria}"]

    if source:
        parts.append(f'SOURCE MATERIAL:\n"""\n{source}\n"""')

    parts.append(f'CONTENT TO EVALUATE:\n"""\n{generated}\n"""')
    parts.append('Return JSON with exactly these keys: "score" (integer 1-100), '
                 '"reasoning" (string), "regeneration_instruction" (string).')

    return [SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="\n\n".join(parts))]


def build_chat_source(query: str, contexts: Optional[List] = None,
                      history: Optional[List[dict]] = None) -> str:
    """
    Turn one chat turn into the "source material" block the judge checks against.

    A chat reply has no single source passage the way a generated resource does, so the
    conversation, the retrieved chunks and the question are assembled into one. The
    parenthetical on the context block is deliberate: it tells the judge the retrieved
    text is a *ceiling*, not merely a hint.
    """
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
    return "\n\n".join(blocks)
