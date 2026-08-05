"""
Session bindings: which PDF a session is about, and what it is for.

    {session_id, doc_id, filename, sha256, kinds, bound_at}

One record per session, with a unique index on session_id -- that uniqueness is what
enforces "one PDF per session" structurally rather than by convention.

`kinds` is a list of what the session was opened for: ["chat"], ["resource"], or both.
The *rules* about kinds live in ingestion/sessions.py, which owns when a binding may be
written and when a command may use one. This module only reads and writes the record.

The hash is stored alongside the id so re-ingesting the *same* file into a session can be
told apart from uploading a different one, without a second lookup.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from .. import config
from .ids import as_object_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_SESSIONS]


def get_session(session_id: str) -> Optional[Dict]:
    """The session's binding record, or None if it has no PDF yet."""
    if not session_id:
        return None
    return _collection().find_one({"session_id": session_id})


def session_doc_id(session_id: str):
    """The document this session is about, or None if nothing is bound to it yet."""
    return (get_session(session_id) or {}).get("doc_id")


def bind_session_document(session_id: str, doc_id, filename: str, sha256: str,
                          kinds=("chat",)) -> None:
    """
    Bind a session to the PDF it will be about, and to what it is for.

    Upsert rather than insert: re-ingesting the same PDF with --force must refresh the
    record instead of colliding with the unique index.
    """
    _collection().update_one(
        {"session_id": session_id},
        {"$set": {"session_id": session_id,
                  "doc_id": as_object_id(doc_id),
                  "filename": filename,
                  "sha256": sha256,
                  "kinds": list(kinds),
                  "bound_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def unbind_session(session_id: str) -> bool:
    """Release a session's PDF, letting a different one be ingested into it."""
    return _collection().delete_one({"session_id": session_id}).deleted_count > 0
