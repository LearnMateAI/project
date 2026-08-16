"""
Node 1 of 3: generate.

Asks the generator for the resource, folding in a critique when this is a retry. Which
prompt, which schema and how to read the reply all come from the Task -- this node is the
same code for all four resource types.

    source (+ critique)  ->  content, attempt

The schema is passed as `response_schema`, so llama.cpp compiles it into a decoding
grammar and malformed JSON becomes impossible on that backend. The HTTP backend forwards
it as `response_format` and falls back to asking plainly, which is why the reply is still
parsed defensively.
"""

import time
from typing import Dict

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_generator_llm, parse_json_reply
from ..storage import content_store
from .helpers import _log, revision_block
from .state import ResourceState
from .tasks import get_task


def generate_node(state: ResourceState) -> Dict:
    """Ask the generator for the resource, folding in a critique when retrying."""
    task = get_task(state["task"])
    attempt = state.get("attempt", 0) + 1

    _log(state, f"[*] Generating {task.name} (attempt {attempt}/{state['max_attempts']})...")

    prompt = task.build_prompt(state["source"], state.get("count", 5))
    if state.get("critique"):
        prompt += revision_block(task, state["critique"], state.get("previous"))

    messages = [
        SystemMessage(content=task.system_prompt),
        HumanMessage(content=prompt),
    ]

    started = time.time()
    try:
        reply = get_generator_llm().invoke(messages, response_schema=task.schema)
        content = task.unwrap(parse_json_reply(reply.content))
        return {"attempt": attempt, "content": content, "started": started,
                "stage": "generated"}
    except Exception as exc:
        # Unparseable or failed output is a failed attempt, not a crash: record it and
        # let `decide` retry with the parse failure as the critique. Logged with
        # stage="parse" so content_store.stage_counts() can show how often the generator,
        # rather than the content, was the problem.
        _log(state, f"[!] Generation failed: {exc}")
        content_store.log_evaluation(
            task.name, attempt, None, False, state["threshold"], stage="parse",
            elapsed=time.time() - started, doc_id=state.get("doc_id"),
            user_id=state.get("user_id"), extra={"error": str(exc)[:300]})
        return {
            "attempt": attempt,
            "content": None,
            "started": started,
            "stage": "parse",
            "passed": False,
            "verdict": None,
            "critique": "Return valid JSON in exactly the requested shape.",
            "previous": None,
            "attempts": [{"attempt": attempt, "stage": "parse", "passed": False,
                          "score": None, "reasons": [str(exc)[:300]], "content": None}],
        }
