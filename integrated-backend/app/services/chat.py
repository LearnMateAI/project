"""
Chat sessions and turns.

A session is one conversation about one PDF. Creating one binds it to a document that has
already been ingested -- which is why this calls `bind_session_document` directly rather
than running `ingest_pdf` again: the chunks and page text already exist, and re-ingesting
would take the "already ingested" fast path only to re-read the file out of GridFS to
discover that.

Session ids are generated here, not accepted from the client. A client-chosen id could
collide with somebody else's session, and the unique index would then make the collision
somebody's problem at bind time rather than at creation.

One turn is one pass through the chat graph: rewrite the question against the history,
retrieve, generate, judge, retry once if the judge rejected it, persist. On the local
backend that is 30-60 seconds, which is why the router runs it as a job.
"""

import uuid
from typing import Dict, List

from learnmate.chat_agent import ChatAgent
from learnmate.ingestion import require_kind
from learnmate.storage import content_store

from . import ownership as access


def _serialize_session(session: Dict, turns: int = None) -> Dict:
    """One session binding, in the shape the frontend reads."""
    bound_at = session.get("bound_at")
    return {
        "session_id": session["session_id"],
        "document_id": str(session.get("doc_id")) if session.get("doc_id") else None,
        "filename": session.get("filename"),
        "title": session.get("title") or session.get("filename"),
        "kinds": session.get("kinds", []),
        "created_at": bound_at.isoformat() if bound_at else None,
        "message_count": turns,
    }


def _serialize_turn(turn: Dict) -> Dict:
    """
    One stored turn, with the audit trail an assistant turn carries.

    `meta` is empty on a user turn and holds mode, score, acceptance, attempt count and
    the pages the answer drew on for an assistant one -- which is what lets the UI mark a
    reply as grounded in the PDF or written from general knowledge.
    """
    created_at = turn.get("created_at")
    meta = turn.get("meta") or {}
    return {
        "id": str(turn["_id"]),
        "role": turn.get("role"),
        "content": turn.get("content", ""),
        "mode": meta.get("mode"),
        "score": meta.get("score"),
        "accepted": meta.get("accepted"),
        "attempts": meta.get("attempts"),
        "pages": meta.get("pages", []),
        "created_at": created_at.isoformat() if created_at else None,
    }


def create_session(user_id: str, doc_id: str, title: str = None) -> Dict:
    """
    Open a conversation about one already-ingested document.

    The document must be Ready: a session bound to a PDF still being processed would
    retrieve nothing and answer every question from general knowledge, which looks like a
    broken assistant rather than an unfinished upload.
    """
    document = access.require_ready_document(user_id, doc_id)

    # Server-generated and unguessable. The user prefix is for reading logs, not for
    # security -- authorisation is the user_id stored on the record.
    session_id = f"s-{user_id[-6:]}-{uuid.uuid4().hex[:12]}"

    content_store.bind_session_document(
        session_id,
        document["_id"],
        document.get("filename", ""),
        document.get("sha256", ""),
        kinds=("chat",),
        user_id=user_id,
        title=title or document.get("filename", "Untitled"),
    )

    return _serialize_session(content_store.get_session(session_id), turns=0)


def list_sessions(user_id: str) -> List[Dict]:
    """The user's conversations, most recent first."""
    return [_serialize_session(session)
            for session in content_store.list_user_sessions(user_id)]


def get_messages(user_id: str, session_id: str) -> List[Dict]:
    """One conversation's transcript, oldest first."""
    access.require_session(user_id, session_id)
    return [_serialize_turn(turn) for turn in content_store.list_turns(session_id)]


def send_message(user_id: str, session_id: str, message: str, evaluate: bool = True,
                 on_progress=None) -> Dict:
    """
    Handle one turn end to end. Slow: 30-60 seconds on the local backend.

    Returns the reply with everything the UI needs to show *how* it was answered --
    which mode, what it scored, which pages it cited -- because "the model said so" and
    "page 41 of your PDF says so" are very different claims to put in front of a student.
    """
    session = access.require_session(user_id, session_id)

    # A session opened for resource generation is not a chat session. The engine's own
    # message names the fix, so it is allowed through unchanged.
    require_kind(session_id, "chat")

    doc_id = session.get("doc_id")
    agent = ChatAgent(
        session_id=session_id,
        doc_id=doc_id,
        user_id=user_id,
        evaluate=evaluate,
        verbose=False,
        on_progress=on_progress,
    )

    result = agent.ask(message)

    return {
        "session_id": session_id,
        "document_id": str(doc_id) if doc_id else None,
        "query": result.get("query"),
        # What the question became once pronouns were resolved against the history. Shown
        # because a follow-up that retrieved badly is almost always a bad rewrite.
        "standalone_query": result.get("standalone_query"),
        "reply": result.get("reply", ""),
        # "pdf" when retrieval found something above the relevance threshold, "general"
        # when it did not and the model answered from its own knowledge.
        "mode": result.get("mode"),
        "top_score": result.get("top_score"),
        "accepted": bool(result.get("accepted")),
        "score": (result.get("verdict") or {}).get("score"),
        "reasoning": (result.get("verdict") or {}).get("reasoning"),
        "attempts": len(result.get("attempts", [])),
        "contexts": [
            {
                "page_number": document.metadata.get("page_number"),
                "text": document.page_content,
                "score": score,
            }
            for document, score in zip(result.get("contexts", []),
                                       result.get("scores", []))
        ],
    }


def delete_session(user_id: str, session_id: str) -> Dict:
    """Delete a conversation: its turns, then its binding."""
    access.require_session(user_id, session_id)
    removed = content_store.clear_history(session_id)
    content_store.unbind_session(session_id)
    return {"removed": True, "messages_deleted": removed}
