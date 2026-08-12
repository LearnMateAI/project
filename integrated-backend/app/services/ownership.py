"""
Access control: the four checks, in one place.

Every route that names a document, a session or a resource goes through a function here
first. Collecting them means the rule is stated once and can be read in one sitting,
rather than being an `if` repeated in fifteen handlers with one of them subtly different.

The rule, in full:

    a document  is readable when the caller has it in their library (user_documents),
                *not* when they uploaded it -- one PDF is stored once and shared, so
                "who uploaded it" is not a question the documents collection can answer
    a session   is the caller's when sessions.user_id matches
    a resource  is the caller's when resources.user_id matches

Session ids are server-generated and unguessable, but unguessable is not an access
control, and a conversation is the most private thing this system stores.
"""

from typing import Dict

from learnmate.storage import content_store, ownership, pdf_store

from ..errors import AccessDenied, NotFound


def require_document(user_id: str, doc_id: str) -> Dict:
    """
    The document, if this user may read it.

    A document they do not have is reported as missing rather than forbidden: whether a
    given id exists at all is not something a stranger should be able to learn.
    """
    document = pdf_store.get_document(doc_id)
    if not document or not ownership.has_access(user_id, document["_id"]):
        raise NotFound("Document not found.")
    return document


def require_ready_document(user_id: str, doc_id: str) -> Dict:
    """
    The document, if this user may read it *and* it has finished processing.

    Generation and chat both need the chunks and the stored page text, neither of which
    exists until ingestion completes -- so this is a clearer failure than an empty
    retrieval three layers down.
    """
    document = require_document(user_id, doc_id)
    status = document.get("processing_status")

    if status == pdf_store.FAILED:
        raise ValueError(
            f"{document.get('filename', 'This document')} could not be processed: "
            f"{document.get('processing_error') or 'unknown error'}"
        )
    if status != pdf_store.READY:
        raise ValueError(
            f"{document.get('filename', 'This document')} is still being processed. "
            f"Please wait for it to finish."
        )
    return document


def require_session(user_id: str, session_id: str) -> Dict:
    """The session binding, if it is this user's."""
    session = content_store.get_session(session_id)
    if not session:
        raise NotFound("Chat session not found.")
    if str(session.get("user_id") or "") != str(user_id):
        raise AccessDenied("You do not have access to this chat session.")
    return session


def require_resource(user_id: str, resource_id: str) -> Dict:
    """The resource, if it is this user's."""
    resource = content_store.get_resource(resource_id)
    if not resource:
        raise NotFound("Resource not found.")
    if str(resource.get("user_id") or "") != str(user_id):
        raise AccessDenied("You do not have access to this resource.")
    return resource
