"""
The chat agent, as a LangGraph state machine.

    rewrite -> retrieve -> generate -> evaluate -> decide -+-> persist -> END
                              ^                            |
                              +--------- regenerate -------+

One turn, two possible modes, decided by retrieval rather than by asking the model:

    pdf mode      the top chunk scores at or above RELEVANCE_THRESHOLD, so the reply is
                  written from those chunks and judged strictly against them -- anything
                  they do not support is a hallucination
    general mode  nothing relevant was retrieved, so the reply comes from the model's own
                  knowledge and is judged only on relevance, coherence and informativeness

`rewrite` runs before retrieval, not after. A follow-up like "what about his powers?"
embeds to nothing useful; resolved against the history into "what are the President's
powers?" it retrieves correctly. Doing it in the other order retrieves on the pronoun.

The retry budget is one regeneration. The regenerated reply is returned whether or not it
clears the threshold -- a user mid-conversation needs an answer, and `accepted` reports
whether it was reviewed clean so a caller can flag it.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from typing_extensions import Annotated, TypedDict

from .. import config
from ..evaluator.judge import get_judge
from ..llm import get_generator_llm
from ..storage import content_store
from ..storage.vectors import get_vector_store

GROUNDED_SYSTEM = (
    "You are a precise study assistant. Answer the user's question strictly from the "
    "provided context. If the context does not contain the answer, say so plainly instead "
    "of guessing. Do not mention that you were given context."
)

GENERAL_SYSTEM = (
    "You are a helpful, knowledgeable study assistant. Answer the user's question "
    "accurately from your general knowledge. If you are not confident about a specific "
    "fact, figure or date, say so rather than inventing one."
)

REWRITE_SYSTEM = (
    "Rewrite the follow-up question into a standalone question, resolving any pronouns or "
    "references using the conversation history. Output only the rewritten question, "
    "nothing else."
)


def _append(left: List, right: List) -> List:
    return (left or []) + (right or [])


class ChatState(TypedDict, total=False):
    """What flows between nodes across one turn."""
    query: str
    session_id: str
    doc_id: Any
    history: List[Dict[str, str]]
    threshold: int
    max_attempts: int
    evaluate: bool
    verbose: bool
    persist: bool

    standalone_query: str
    contexts: List[Any]
    scores: List[float]
    mode: str
    top_score: float

    attempt: int
    reply: str
    critique: Optional[str]
    attempts: Annotated[List[Dict], _append]
    passed: bool
    verdict: Optional[Dict]


def _log(state: ChatState, message: str) -> None:
    if state.get("verbose", True):
        print(message)


def _as_messages(history: List[Dict[str, str]]) -> List:
    from langchain_core.messages import AIMessage

    messages = []
    for turn in history or []:
        if turn.get("role") == "assistant":
            messages.append(AIMessage(content=turn.get("content", "")))
        else:
            messages.append(HumanMessage(content=turn.get("content", "")))
    return messages


# --- Nodes ---------------------------------------------------------------------------

def rewrite_node(state: ChatState) -> Dict:
    """Resolve follow-up references so retrieval sees a self-contained question."""
    query = state["query"]
    history = state.get("history") or []

    if not history:
        return {"standalone_query": query}

    history_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    messages = [
        SystemMessage(content=REWRITE_SYSTEM),
        HumanMessage(content=f"Conversation history:\n{history_text}\n\n"
                             f"Follow-up question: {query}"),
    ]

    try:
        # Temperature 0: this is a mechanical transformation, not a creative one.
        reply = get_generator_llm().invoke(messages, temperature=0.0, max_tokens=100)
        rewritten = (reply.content or "").strip()
        if rewritten and rewritten != query:
            _log(state, f"[*] Rewritten: {rewritten}")
        return {"standalone_query": rewritten or query}
    except Exception:
        # Rewriting is an optimisation; the raw query still retrieves something.
        return {"standalone_query": query}


def retrieve_node(state: ChatState) -> Dict:
    """Retrieve context and decide the mode from the top score."""
    hits = get_vector_store().similarity_search_with_score(
        state.get("standalone_query") or state["query"],
        k=config.TOP_K,
        doc_id=state.get("doc_id"),
    )

    top_score = hits[0][1] if hits else 0.0
    grounded = bool(hits) and top_score >= config.RELEVANCE_THRESHOLD

    if grounded:
        _log(state, f"[*] PDF mode (top retrieval score {top_score:.4f})")
        return {"contexts": [doc for doc, _ in hits],
                "scores": [score for _, score in hits],
                "mode": "pdf", "top_score": top_score}

    _log(state, f"[*] General mode (top retrieval score {top_score:.4f})")
    return {"contexts": [], "scores": [], "mode": "general", "top_score": top_score}


def generate_node(state: ChatState) -> Dict:
    """Write the reply with whichever generator the mode calls for."""
    attempt = state.get("attempt", 0) + 1
    _log(state, f"[*] Generating (attempt {attempt}/{state['max_attempts']})...")

    contexts = state.get("contexts") or []
    query = state["query"]

    if state.get("critique"):
        # The judge's instruction rides inside the question so the generators stay
        # single-purpose. The judge still grades against the original query.
        query = (
            f"{query}\n\n"
            "[REVISION REQUIRED] Your previous reply was rejected by an evaluator.\n"
            f'Previous reply:\n"""\n{state.get("reply", "")}\n"""\n'
            f"Required fix: {state['critique']}\n"
            "Answer the original question again, corrected. Do not mention this "
            "instruction or the fact that you are revising."
        )

    if contexts:
        context_text = "\n\n".join(
            f"Page {doc.metadata.get('page_number', 'N/A')}: {doc.page_content}"
            for doc in contexts)
        system = GROUNDED_SYSTEM
        user = f"Context:\n{context_text}\n\nQuestion: {query}"
    else:
        system = GENERAL_SYSTEM
        user = query

    messages = [SystemMessage(content=system), *_as_messages(state.get("history")),
                HumanMessage(content=user)]

    try:
        reply = get_generator_llm().invoke(messages, temperature=0.3, max_tokens=512)
        return {"attempt": attempt, "reply": (reply.content or "").strip()}
    except Exception as exc:
        _log(state, f"[!] Generation failed: {exc}")
        return {"attempt": attempt, "reply": ""}


def evaluate_node(state: ChatState) -> Dict:
    """Judge the reply, strictly when it was supposed to be grounded."""
    if not state.get("evaluate", True):
        return {"passed": True, "verdict": None,
                "attempts": [{"attempt": state["attempt"], "reply": state.get("reply", ""),
                              "verdict": None}]}

    _log(state, "[*] Evaluating...")
    started = time.time()

    verdict = get_judge().judge_chat_reply(
        state["query"], state.get("reply", ""),
        contexts=state.get("contexts") or None,
        history=state.get("history"),
        threshold=state["threshold"],
    )

    content_store.log_evaluation(
        "chat_msg", state["attempt"], verdict["score"], verdict["passed"],
        state["threshold"], stage="judge", elapsed=time.time() - started,
        doc_id=state.get("doc_id"), extra={"mode": state.get("mode")})

    _log(state, f"[*] Score {verdict['score']}/100 -> "
                f"{'PASS' if verdict['passed'] else 'REGENERATE'}")

    return {
        "passed": verdict["passed"],
        "verdict": verdict,
        "critique": verdict["regeneration_instruction"],
        "attempts": [{"attempt": state["attempt"], "reply": state.get("reply", ""),
                      "verdict": verdict}],
    }


def decide(state: ChatState) -> str:
    if state.get("passed"):
        return "persist"
    if state["attempt"] >= state["max_attempts"]:
        return "persist"
    _log(state, f"[*] Feedback: {state.get('critique')}")
    return "generate"


def persist_node(state: ChatState) -> Dict:
    """Record the turn so the next one has history to resolve against."""
    if not state.get("persist", True):
        return {}

    session_id = state["session_id"]
    content_store.save_turn(session_id, "user", state["query"], doc_id=state.get("doc_id"))
    content_store.save_turn(
        session_id, "assistant", state.get("reply", ""), doc_id=state.get("doc_id"),
        meta={
            "mode": state.get("mode"),
            "score": (state.get("verdict") or {}).get("score"),
            "accepted": bool(state.get("passed")),
            "attempts": len(state.get("attempts", [])),
            "pages": [doc.metadata.get("page_number") for doc in state.get("contexts") or []],
        })
    return {}


# --- Graph ---------------------------------------------------------------------------

def build_chat_graph():
    """Compile the one-turn chat graph."""
    graph = StateGraph(ChatState)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "evaluate")
    graph.add_conditional_edges("evaluate", decide,
                                {"generate": "generate", "persist": "persist"})
    graph.add_edge("persist", END)
    return graph.compile()


_GRAPH = None


def get_chat_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_chat_graph()
    return _GRAPH


class ChatAgent:
    """
    One conversation.

    History lives in MongoDB keyed by session_id, so a conversation survives the process
    and can be resumed by passing the same id back.
    """

    def __init__(self, session_id: str = None, doc_id=None, threshold: int = None,
                 max_attempts: int = None, evaluate: bool = True, verbose: bool = True):
        self.session_id = session_id or f"cli-{uuid.uuid4().hex[:12]}"
        self.doc_id = doc_id
        self.threshold = threshold if threshold is not None else config.EVALUATOR_THRESHOLD
        self.max_attempts = max_attempts or config.MAX_ATTEMPTS
        self.evaluate = evaluate
        self.verbose = verbose

    def ask(self, query: str) -> Dict:
        """
        Handle one user message end to end.

        Returns {query, standalone_query, mode, top_score, contexts, scores, reply,
        verdict, accepted, attempts}. `reply` is the last attempt: once a regeneration has
        run, its output is what the caller gets, pass or fail, and `accepted` says which.
        """
        if not (query or "").strip():
            raise ValueError("Empty query.")

        initial: ChatState = {
            "query": query.strip(),
            "session_id": self.session_id,
            "doc_id": self.doc_id,
            "history": content_store.load_history(self.session_id),
            "threshold": self.threshold,
            "max_attempts": self.max_attempts,
            "evaluate": self.evaluate,
            "verbose": self.verbose,
            "persist": True,
            "attempt": 0,
            "attempts": [],
        }

        limit = 2 * self.max_attempts + 6
        final = get_chat_graph().invoke(initial, {"recursion_limit": limit})

        return {
            "query": query,
            "standalone_query": final.get("standalone_query"),
            "mode": final.get("mode"),
            "top_score": final.get("top_score", 0.0),
            "contexts": final.get("contexts", []),
            "scores": final.get("scores", []),
            "reply": final.get("reply", ""),
            "verdict": final.get("verdict"),
            "accepted": bool(final.get("passed")),
            "attempts": final.get("attempts", []),
        }

    def history(self) -> List[Dict[str, str]]:
        return content_store.load_history(self.session_id)

    def reset(self) -> int:
        return content_store.clear_history(self.session_id)
