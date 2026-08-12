"""
The dependency every protected route depends on.

    user: dict = Depends(get_current_user)

Reads `Authorization: Bearer <token>`, verifies it, and hands back {id, email}. Every
route that touches a document, a session, a resource or a job takes this, and every
service function takes the resulting `user_id` -- that pairing is what makes access
control something the type signature reminds you about rather than something you have to
remember.

Two kinds of token are accepted: one this server signed itself (HS256), and one Keycloak
signed (RS256). The local kind is tried first and is the only thing checked when
KEYCLOAK_ENABLED is off -- a token in the wrong format is rejected by PyJWT on the
algorithm mismatch alone, before any cryptographic work happens, so this costs nothing for
the common case. Whichever kind verifies, this function's job is to make the two
indistinguishable to everything downstream: ownership.py and every service function only
ever see {id, email} and have never heard of Keycloak.
"""

from typing import Dict

import jwt
from fastapi import Header, HTTPException

from learnmate.storage import users as user_store

from . import config
from .auth.keycloak import decode_keycloak_token
from .auth.security import decode_access_token


def _from_local_payload(payload: dict) -> Dict[str, str]:
    user_id = payload.get("sub")
    if not user_id:
        # A token this server signed always has a subject; one without is not ours.
        raise jwt.InvalidTokenError("Token has no subject.")
    return {"id": str(user_id), "email": payload.get("email", "")}


def _from_keycloak_payload(payload: dict) -> Dict[str, str]:
    """
    Turn a verified Keycloak identity into this app's kind of user.

    Finds the local account already linked to this Keycloak subject, or provisions one
    on first login, then hands back the exact same shape _from_local_payload does.
    Everything downstream of this function cannot tell which login path was used.
    """
    sub = payload.get("sub")
    if not sub:
        raise jwt.InvalidTokenError("Keycloak token has no subject.")

    user = user_store.get_by_keycloak_sub(sub)
    if user is None:
        user = user_store.create_keycloak_user(
            sub,
            name=payload.get("name", payload.get("preferred_username", "")),
            email=payload.get("email", ""),
        )
    return {"id": str(user["_id"]), "email": user.get("email", "")}


def get_current_user(authorization: str = Header(None)) -> Dict[str, str]:
    """FastAPI dependency: the authenticated caller, or a 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization[len("Bearer "):].strip()

    try:
        return _from_local_payload(decode_access_token(token))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        pass  # Not our HS256 format -- fall through and try Keycloak below.

    if config.KEYCLOAK_ENABLED:
        try:
            return _from_keycloak_payload(decode_keycloak_token(token))
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
        except jwt.InvalidTokenError:
            pass

    raise HTTPException(status_code=401, detail="Invalid authentication token.")
