"""
Turning whatever a caller passed into a MongoDB ObjectId.

Document ids cross a lot of boundaries in this system -- a CLI argument, a report dict, a
Qdrant payload, an HTTP request -- and arrive as ObjectId, hex string, or something that
is neither. Every module that queries by id needs the same coercion, so it lives here
once.

Two variants, because two different failures are wanted:

    as_object_id   returns the value unchanged when it is not an id, so a query on it
                   simply matches nothing instead of raising mid-write
    coerce_id      returns None, so a lookup can answer "no such document" cleanly
"""

from typing import Any, Optional, Union

from bson import ObjectId
from bson.errors import InvalidId


def as_object_id(value) -> Union[ObjectId, Any]:
    """Coerce to ObjectId, passing the original through when it cannot be one."""
    if isinstance(value, ObjectId) or value is None:
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return value


def coerce_id(doc_id: Union[str, ObjectId]) -> Optional[ObjectId]:
    """Accept an ObjectId or its hex string; return None if it is neither."""
    if isinstance(doc_id, ObjectId):
        return doc_id
    try:
        return ObjectId(str(doc_id))
    except (InvalidId, TypeError):
        return None
