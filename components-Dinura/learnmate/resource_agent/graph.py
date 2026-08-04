"""
The resource-generation agent, as a LangGraph state machine.

    generate -> check -> decide -+-> persist -> END
        ^                        |
        +------ regenerate ------+

`check` runs two gates, cheapest first:

    structural validators   plain Python, microseconds
    LLM judge               ~25 seconds

Most bad generations fail mechanically -- three options instead of four, a correct_answer
that appears in no option, an empty summary -- so the judge is only ever spent on content
that is already well-formed.

`decide` is the only place the loop can end. It stops on a pass or on the attempt budget,
and the budget is 2: one generation plus one regeneration. Raising it is not just slower;
a 3B judge tends to oscillate rather than converge over more rounds, and the third attempt
is usually a worse version of the first.

Expressing this as a graph rather than a for-loop is what makes the flow inspectable --
every node's decision lands in the state, so a run that produced bad output can be read
back afterwards instead of guessed at.
"""

import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from typing_extensions import Annotated, TypedDict

from .. import config
from ..evaluator import validators
from ..evaluator.judge import get_judge
from ..llm import get_generator_llm, parse_json_reply
from ..storage import content_store
from .tasks import Task, get_task


def _append(left: List, right: List) -> List:
    """Reducer: attempts accumulate across loop iterations instead of overwriting."""
    return (left or []) + (right or [])


class ResourceState(TypedDict, total=False):
    """What flows between nodes. `attempts` is the audit trail of the whole run."""
    task: str
    source: str
    count: int
    doc_id: Any
    threshold: int
    max_attempts: int
    evaluate: bool
    verbose: bool

    attempt: int
    content: Any
    critique: Optional[str]
    previous: Any

    attempts: Annotated[List[Dict], _append]
    stage: str
    passed: bool
    verdict: Optional[Dict]
    started: float
    resource_id: Optional[str]
    persist: bool


def _log(state: ResourceState, message: str) -> None:
    if state.get("verbose", True):
        print(message)


def _revision_block(task: Task, critique: str, previous: Any) -> str:
    """
    Append the judge's instruction to the next prompt.

    The rejected attempt is included so the model revises rather than starting over: given
    only the instruction it tends to discard the good items along with the bad one.
    """
    block = ("\n\n[REVISION REQUIRED] An evaluator rejected your previous attempt.\n"
             f"Required fix: {critique}\n")
    if previous is not None:
        block += f'Your previous attempt:\n"""\n{task.render(previous)[:2000]}\n"""\n'
    block += ("Produce the whole resource again with that fix applied, keeping everything "
              "the evaluator did not object to. Do not mention this instruction.")
    return block


# --- Nodes ---------------------------------------------------------------------------

def generate_node(state: ResourceState) -> Dict:
    """Ask the generator for the resource, folding in a critique when retrying."""
    task = get_task(state["task"])
    attempt = state.get("attempt", 0) + 1

    _log(state, f"[*] Generating {task.name} (attempt {attempt}/{state['max_attempts']})...")

    prompt = task.build_prompt(state["source"], state.get("count", 5))
    if state.get("critique"):
        prompt += _revision_block(task, state["critique"], state.get("previous"))

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
        # let `decide` retry with the parse failure as the critique.
        _log(state, f"[!] Generation failed: {exc}")
        content_store.log_evaluation(
            task.name, attempt, None, False, state["threshold"], stage="parse",
            elapsed=time.time() - started, doc_id=state.get("doc_id"),
            extra={"error": str(exc)[:300]})
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


def check_node(state: ResourceState) -> Dict:
    """Structural gate, then the judge. The judge only sees content that passed the gate."""
    if state.get("stage") == "parse":
        return {}  # generation already failed; nothing to check

    task = get_task(state["task"])
    attempt = state["attempt"]
    content = state.get("content")
    started = state.get("started", time.time())

    ok, reasons = validators.validate(task.name, content)
    if not ok:
        _log(state, f"[*] Structural check FAILED: {'; '.join(reasons)}")
        content_store.log_evaluation(
            task.name, attempt, None, False, state["threshold"], stage="validator",
            elapsed=time.time() - started, doc_id=state.get("doc_id"),
            extra={"reasons": reasons})
        return {
            "stage": "validator",
            "passed": False,
            "verdict": None,
            "critique": "Fix these structural problems and change nothing else: "
                        + "; ".join(reasons),
            "previous": content,
            "attempts": [{"attempt": attempt, "stage": "validator", "passed": False,
                          "score": None, "reasons": reasons, "content": content}],
        }

    if not state.get("evaluate", True):
        # Evaluation off: generation is intact and both gates are skipped, which is how
        # you measure what evaluation is actually costing.
        return {
            "stage": "skipped", "passed": True, "verdict": None, "critique": None,
            "attempts": [{"attempt": attempt, "stage": "skipped", "passed": True,
                          "score": None, "reasons": [], "content": content}],
        }

    _log(state, "[*] Structural check passed. Judging...")
    verdict = get_judge().judge(
        task.name, task.render(content), source=state["source"],
        threshold=state["threshold"])

    content_store.log_evaluation(
        task.name, attempt, verdict["score"], verdict["passed"], state["threshold"],
        stage="judge", elapsed=time.time() - started, doc_id=state.get("doc_id"))
    _log(state, f"[*] Score {verdict['score']}/100 -> "
                f"{'PASS' if verdict['passed'] else 'REGENERATE'}")

    return {
        "stage": "judge",
        "passed": verdict["passed"],
        "verdict": verdict,
        "critique": verdict["regeneration_instruction"],
        "previous": content,
        "attempts": [{"attempt": attempt, "stage": "judge", "passed": verdict["passed"],
                      "score": verdict["score"], "reasons": [], "content": content,
                      "verdict": verdict}],
    }


def decide(state: ResourceState) -> str:
    """Stop on a pass or on the attempt budget; otherwise go round again."""
    if state.get("passed"):
        return "persist"
    if state["attempt"] >= state["max_attempts"]:
        return "persist"
    _log(state, f"[*] Feedback: {state.get('critique')}")
    return "generate"


def persist_node(state: ResourceState) -> Dict:
    """
    Store the resource with its whole attempt trail.

    The last attempt is the answer, pass or fail -- once a regeneration has run, its
    output is what the caller gets. Earlier attempts stay in the record so a run that
    needed a retry, and what the judge objected to, remains answerable afterwards.
    """
    attempts = state.get("attempts", [])
    final = attempts[-1] if attempts else {}

    if not state.get("persist", True):
        return {"content": final.get("content"), "resource_id": None}

    resource_id = content_store.save_resource(
        doc_id=state.get("doc_id"),
        task=state["task"],
        content=final.get("content"),
        accepted=bool(state.get("passed")),
        attempts=attempts,
        verdict=state.get("verdict"),
        source_preview=state.get("source", ""),
        params={"count": state.get("count"), "threshold": state["threshold"],
                "evaluated": state.get("evaluate", True)},
    )
    _log(state, f"[+] Stored resource {resource_id}")
    return {"content": final.get("content"), "resource_id": str(resource_id)}


# --- Graph ---------------------------------------------------------------------------

def build_resource_graph():
    """Compile the generate/check/retry graph."""
    graph = StateGraph(ResourceState)
    graph.add_node("generate", generate_node)
    graph.add_node("check", check_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "check")
    graph.add_conditional_edges("check", decide,
                                {"generate": "generate", "persist": "persist"})
    graph.add_edge("persist", END)
    return graph.compile()


_GRAPH = None


def get_resource_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_resource_graph()
    return _GRAPH


def generate_resource(task: str, source: str, count: int = 5, doc_id=None,
                      threshold: int = None, max_attempts: int = None,
                      evaluate: bool = True, persist: bool = True,
                      verbose: bool = True) -> Dict:
    """
    Generate one study resource end to end.

    Returns {task, content, accepted, verdict, attempts, resource_id}, where `content` is
    the last attempt and `attempts` holds the whole trail in order.
    """
    get_task(task)  # fail fast on an unknown task, before loading any model

    if not (source or "").strip():
        raise ValueError("Cannot generate from empty source text.")

    initial: ResourceState = {
        "task": task,
        "source": source,
        "count": count,
        "doc_id": doc_id,
        "threshold": threshold if threshold is not None else config.EVALUATOR_THRESHOLD,
        "max_attempts": max_attempts or config.MAX_ATTEMPTS,
        "evaluate": evaluate,
        "persist": persist,
        "verbose": verbose,
        "attempt": 0,
        "attempts": [],
    }

    # The graph loops, so LangGraph's default recursion budget has to cover
    # attempts x (generate + check) plus persist.
    limit = 2 * initial["max_attempts"] + 4
    final = get_resource_graph().invoke(initial, {"recursion_limit": limit})

    return {
        "task": task,
        "content": final.get("content"),
        "accepted": bool(final.get("passed")),
        "verdict": final.get("verdict"),
        "attempts": final.get("attempts", []),
        "resource_id": final.get("resource_id"),
    }
