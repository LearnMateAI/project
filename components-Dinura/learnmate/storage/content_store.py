"""
Everything the agents produce and read back: the facade over four modules.

    sessions.py     which PDF a session is about, and what it is for
    history.py      chat turns
    resources.py    generated MCQs, questions, key points and summaries
    evaluations.py  the verdict log, and the statistics read off it

Kept as one importable name because every node in both agents already reads
`content_store.save_turn(...)`, `content_store.log_evaluation(...)`. Import the specific
module when you care which collection you are touching.
"""

from .evaluations import evaluation_stats, log_evaluation, stage_counts
from .history import clear_history, list_sessions, load_history, save_turn
from .resources import get_resource, list_resources, save_resource
from .sessions import (
    bind_session_document,
    get_session,
    session_doc_id,
    unbind_session,
)

__all__ = [
    "bind_session_document",
    "clear_history",
    "evaluation_stats",
    "get_resource",
    "get_session",
    "list_resources",
    "list_sessions",
    "load_history",
    "log_evaluation",
    "save_resource",
    "save_turn",
    "session_doc_id",
    "stage_counts",
    "unbind_session",
]
