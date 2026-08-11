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
from .history import (
    clear_history,
    count_turns,
    list_sessions,
    list_turns,
    load_history,
    save_turn,
)
from .resources import (
    count_by_task,
    delete_resource,
    get_resource,
    list_resources,
    save_resource,
)
from .sessions import (
    bind_session_document,
    count_user_sessions,
    get_session,
    list_user_sessions,
    session_doc_id,
    unbind_session,
)

__all__ = [
    "bind_session_document",
    "clear_history",
    "count_by_task",
    "count_turns",
    "count_user_sessions",
    "delete_resource",
    "evaluation_stats",
    "get_resource",
    "get_session",
    "list_resources",
    "list_sessions",
    "list_turns",
    "list_user_sessions",
    "load_history",
    "log_evaluation",
    "save_resource",
    "save_turn",
    "session_doc_id",
    "stage_counts",
    "unbind_session",
]
