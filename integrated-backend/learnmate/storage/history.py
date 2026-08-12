"""
Chat history: one row per turn.

    {session_id, role, content, doc_id, meta, created_at}

This is what makes a conversation outlive the process. The chat agent's `rewrite` node
resolves pronouns against exactly what is stored here, so a session resumed tomorrow
behaves like one that never stopped.

`meta` on an assistant turn carries the audit trail beside the text -- which mode
answered, what it scored, whether it was accepted, how many attempts it took, and which
pages it drew on.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .. import config
from .ids import as_object_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_CHAT_TURNS]


def save_turn(session_id: str, role: str, content: str, doc_id=None,
              meta: Optional[Dict] = None, user_id: str = None) -> None:
    """Append one chat turn."""
    _collection().insert_one({
        "session_id": session_id,
        "user_id": str(user_id) if user_id else None,
        "role": role,
        "content": content,
        "doc_id": as_object_id(doc_id),
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc),
    })


def load_history(session_id: str, max_turns: int = None) -> List[Dict[str, str]]:
    """
    The last N user+assistant pairs, oldest first.

    Fetched newest-first then reversed: with the index on (session_id, created_at) that is
    a bounded scan, where sorting the whole session forward and taking the tail is not.

    Bounded rather than complete because history goes into every prompt -- an unbounded
    conversation would eventually crowd the retrieved context out of a 4k window.
    """
    max_turns = max_turns or config.MAX_HISTORY_TURNS
    rows = list(_collection()
                .find({"session_id": session_id}, {"role": 1, "content": 1})
                .sort("created_at", -1)
                .limit(max_turns * 2))
    rows.reverse()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def list_turns(session_id: str, limit: int = 200) -> List[Dict]:
    """
    Every stored turn of one session, oldest first, with its `meta` intact.

    `load_history` deliberately returns only role and content, because that is all a
    prompt may contain. A transcript in the UI wants more than that -- which mode
    answered, what it scored, which pages it drew on -- so it reads this instead.
    """
    return list(_collection()
                .find({"session_id": session_id})
                .sort("created_at", 1)
                .limit(limit))


def count_turns(user_id: str, role: str = None) -> int:
    """How many turns this user has exchanged. For the analytics page."""
    query: Dict = {"user_id": str(user_id)}
    if role:
        query["role"] = role
    return _collection().count_documents(query)


def clear_history(session_id: str) -> int:
    """Forget a session's turns. Returns how many were removed."""
    return _collection().delete_many({"session_id": session_id}).deleted_count


def list_sessions(limit: int = 20) -> List[Dict]:
    """Known chat sessions, most recently active first."""
    pipeline = [
        {"$group": {"_id": "$session_id", "turns": {"$sum": 1},
                    "last": {"$max": "$created_at"}}},
        {"$sort": {"last": -1}},
        {"$limit": limit},
    ]
    return list(_collection().aggregate(pipeline))
