"""
Registered accounts.

    {_id, name, email, password_hash, created_at}

This module owns the collection and nothing else: it never sees a plaintext password and
has no opinion on what makes one acceptable. Hashing lives in app/auth/security.py and the
rules in app/auth/users.py, so the policy can change without touching persistence.

The email is stored lower-cased and stripped, and the unique index in indexes.py is what
makes "this address is taken" a fact about the database rather than a check that can race
between two simultaneous registrations.
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Union

from bson import ObjectId

from .. import config
from .ids import coerce_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_USERS]


def normalise_email(email: str) -> str:
    """The stored form of an address: what both writing and looking one up must use."""
    return (email or "").strip().lower()


def create_user(name: str, email: str, password_hash: str) -> Dict:
    """
    Insert one account and return it.

    Raises pymongo's DuplicateKeyError when the address is taken; the caller turns that
    into the 409 rather than pre-checking, which would leave a window between the check
    and the insert.
    """
    record = {
        "name": (name or "").strip(),
        "email": normalise_email(email),
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc),
    }
    record["_id"] = _collection().insert_one(record).inserted_id
    return record


def get_by_email(email: str) -> Optional[Dict]:
    """Look up an account by address, in its stored form."""
    return _collection().find_one({"email": normalise_email(email)})


def get_by_id(user_id: Union[str, ObjectId]) -> Optional[Dict]:
    """Look up an account by id. Returns None for an id that is not one."""
    oid = coerce_id(user_id)
    if oid is None:
        return None
    return _collection().find_one({"_id": oid})


def public_view(user: Dict) -> Dict:
    """
    The shape of a user everywhere outside this module.

    One function so the password hash cannot leak into a response by someone handing back
    a raw record.
    """
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
    }
