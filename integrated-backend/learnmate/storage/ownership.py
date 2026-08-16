"""
Who may see which document.

    {user_id, doc_id, filename, subject, added_at}   unique on (user_id, doc_id)

This collection exists because of a property of `documents` that is worth keeping: a
document is identified by the SHA-256 of its bytes, with a unique index on it, so the same
PDF uploaded by five students is stored once, extracted once, and embedded once. Embedding
is the expensive step in this whole system -- a few thousand chunks through a CPU model --
and paying it five times to write five nearly identical rows would be the wrong trade.

That is also why ownership cannot be a field *on* the document: a shared record cannot
carry one owner. So the two questions are stored separately --

    documents        what this PDF is        one row per set of bytes
    user_documents   whose library it is in  one row per person per document

-- and every access check in the API asks this collection, never the document.

`filename` and `subject` are per-user on purpose. Two people can upload the same bytes
under different names and file them under different subjects, and each should see their
own.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from bson import ObjectId

from .. import config
from .ids import as_object_id, coerce_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_USER_DOCUMENTS]


def link(user_id: str, doc_id, filename: str, subject: str = "General") -> Dict:
    """
    Put a document in a user's library, or refresh the entry if it is already there.

    Upsert rather than insert: re-uploading a PDF you already have is a no-op that may
    update the subject, not an error.
    """
    now = datetime.now(timezone.utc)
    record = {
        "user_id": str(user_id),
        "doc_id": as_object_id(doc_id),
        "filename": filename,
        "subject": subject or "General",
    }
    _collection().update_one(
        {"user_id": record["user_id"], "doc_id": record["doc_id"]},
        {"$set": record, "$setOnInsert": {"added_at": now}},
        upsert=True,
    )
    return {**record, "added_at": now}


def unlink(user_id: str, doc_id) -> bool:
    """Take a document out of one user's library. Nothing else is deleted here."""
    result = _collection().delete_one(
        {"user_id": str(user_id), "doc_id": as_object_id(doc_id)})
    return result.deleted_count > 0


def get_link(user_id: str, doc_id) -> Optional[Dict]:
    """The user's entry for one document, or None if it is not in their library."""
    oid = coerce_id(doc_id)
    if oid is None:
        return None
    return _collection().find_one({"user_id": str(user_id), "doc_id": oid})


def has_access(user_id: str, doc_id) -> bool:
    """Whether this user may read this document. The only access check the API makes."""
    return get_link(user_id, doc_id) is not None


def list_links(user_id: str, limit: int = 100) -> List[Dict]:
    """One user's library, most recently added first."""
    return list(_collection()
                .find({"user_id": str(user_id)})
                .sort("added_at", -1)
                .limit(limit))


def count_links(user_id: str) -> int:
    """How many documents this user has. For the analytics page."""
    return _collection().count_documents({"user_id": str(user_id)})


def owner_count(doc_id: Union[str, ObjectId]) -> int:
    """
    How many libraries hold this document.

    What makes deletion safe: dropping the bytes, pages, chunks and vectors is only
    correct once this reaches zero, or one person deleting a shared PDF would silently
    break it for everyone else who uploaded it.
    """
    oid = coerce_id(doc_id)
    if oid is None:
        return 0
    return _collection().count_documents({"doc_id": oid})
