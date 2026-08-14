"""
The public face of the chat agent.

`ChatAgent` is the only thing callers touch. It holds the per-conversation settings,
loads history, runs one pass of the graph per message, and flattens the final state into
a plain dict.
"""

import uuid
from typing import Dict, List

from .. import config
from ..storage import content_store
from .graph import get_chat_graph
from .state import ChatState


class ChatAgent:
    """
    One conversation.

    History lives in MongoDB keyed by session_id, so a conversation survives the process
    and can be resumed by passing the same id back.
    """

    def __init__(self, session_id: str = None, doc_id=None, threshold: int = None,
                 max_attempts: int = None, evaluate: bool = True, verbose: bool = True,
                 user_id: str = None, on_progress=None, on_token=None):
        # A generated id gives an anonymous CLI session somewhere to store history,
        # without the caller having to invent one.
        self.session_id = session_id or f"cli-{uuid.uuid4().hex[:12]}"
        self.doc_id = doc_id
        # Stamped on every turn this agent writes. The API always passes it; the CLI
        # leaves it None, and those turns simply belong to nobody.
        self.user_id = user_id
        # `is not None` rather than `or`: threshold=0 is a legitimate "accept anything".
        self.threshold = threshold if threshold is not None else config.EVALUATOR_THRESHOLD
        self.max_attempts = max_attempts or config.MAX_ATTEMPTS
        self.evaluate = evaluate
        self.verbose = verbose
        # Where the running commentary goes when nobody is watching stdout -- see
        # helpers._log. The API points this at the job record.
        self.on_progress = on_progress
        # The reply itself, as it is written. Distinct from on_progress because the two
        # are read differently: commentary replaces the previous line, the reply is the
        # answer taking shape. See helpers._emit_token.
        self.on_token = on_token

    def ask(self, query: str) -> Dict:
        """
        Handle one user message end to end.

        Returns {query, standalone_query, mode, top_score, contexts, scores, reply,
        verdict, accepted, attempts}. `reply` is the *best-scoring* attempt, not
        necessarily the last one -- see persist.best_attempt, which picks it. `attempts`
        holds every version with its verdict, so the ones not chosen stay inspectable.
        """
        if not (query or "").strip():
            raise ValueError("Empty query.")

        # History is re-read from Mongo every turn rather than cached in the object, so
        # two processes sharing a session_id stay consistent.
        initial: ChatState = {
            "query": query.strip(),
            "session_id": self.session_id,
            "user_id": self.user_id,
            "doc_id": self.doc_id,
            "history": content_store.load_history(self.session_id),
            "threshold": self.threshold,
            "max_attempts": self.max_attempts,
            "evaluate": self.evaluate,
            "verbose": self.verbose,
            "on_progress": self.on_progress,
            "on_token": self.on_token,
            "persist": True,
            "attempt": 0,
            "attempts": [],
        }

        # LangGraph counts every node execution against this limit and raises if it is
        # exceeded. Two nodes per attempt (generate + evaluate) plus headroom for the
        # linear nodes -- a safety net in case `decide` ever fails to terminate.
        limit = 2 * self.max_attempts + 6
        final = get_chat_graph().invoke(initial, {"recursion_limit": limit})

        # Flatten the state into a stable return shape. Callers depend on these keys, so
        # they are listed explicitly rather than handing back the raw state dict.
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
        """Every turn stored for this session, oldest first."""
        return content_store.load_history(self.session_id)

    def reset(self) -> int:
        """Wipe this session's history. Returns how many turns were deleted."""
        return content_store.clear_history(self.session_id)
