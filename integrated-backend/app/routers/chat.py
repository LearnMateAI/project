"""
Chat: conversations about one document.

A session is opened against an already-ingested PDF, and every message in it is answered
by the chat graph -- rewrite the question against the history, retrieve, generate, judge,
retry once if the judge rejected it. That is 30-60 seconds on the local backend, so
sending a message returns **202 with a job id** and the reply arrives in the finished
job's `result`.

The reply carries more than text, and the extra fields are the point:

    mode        "pdf" when retrieval found something above the relevance threshold,
                "general" when nothing matched and the model answered from its own
                knowledge. A student needs to know which of those they are reading.
    contexts    the chunks it was written from, with page numbers, so the answer can be
                checked against the document rather than trusted.
    score       what the judge gave it, and `accepted` whether that cleared the threshold.
"""

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..jobs import enqueue
from ..schemas import CreateSessionRequest, SendMessageRequest
from ..services import chat as service
from ..services import ownership as access

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/sessions", status_code=201)
def create_session(payload: CreateSessionRequest, user: dict = Depends(get_current_user)):
    """
    Open a conversation about one document.

    The document must have finished processing: a session bound to a PDF that is still
    being embedded would retrieve nothing and answer everything from general knowledge,
    which reads as a broken assistant rather than an unfinished upload.
    """
    return service.create_session(user["id"], payload.document_id, payload.title)


@router.get("/sessions")
def list_sessions(user: dict = Depends(get_current_user)):
    """This user's conversations, most recent first."""
    return service.list_sessions(user["id"])


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, user: dict = Depends(get_current_user)):
    """The transcript, oldest first, with each reply's mode, score and cited pages."""
    return service.get_messages(user["id"], session_id)


@router.post("/sessions/{session_id}/messages", status_code=202)
def send_message(session_id: str, payload: SendMessageRequest,
                 user: dict = Depends(get_current_user)):
    """
    Queue one turn.

    Ownership is checked here, before queueing, so posting into somebody else's session
    is a 403 now rather than a job that fails later.
    """
    access.require_session(user["id"], session_id)

    job = enqueue(
        user["id"], "chat",
        {"session_id": session_id, "message": payload.message,
         "evaluate": payload.evaluate},
        message="Waiting to answer.",
    )

    return {"job_id": str(job["_id"]), "status": job["status"], "kind": "chat"}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation and everything said in it. The document is untouched."""
    return service.delete_session(user["id"], session_id)
