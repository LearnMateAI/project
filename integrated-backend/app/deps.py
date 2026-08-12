"""
The dependency every protected route depends on.

    user: dict = Depends(get_current_user)

Reads `Authorization: Bearer <token>`, verifies it, and hands back {id, email}. Every
route that touches a document, a session, a resource or a job takes this, and every
service function takes the resulting `user_id` -- that pairing is what makes access
control something the type signature reminds you about rather than something you have to
remember.

The two failure modes are separated on purpose: an expired token means "log in again" and
the client can act on it, while an invalid one means the token is wrong or tampered with.
Collapsing both into one message would make a routine session timeout look like an attack.
"""

from typing import Dict

import jwt
from fastapi import Header, HTTPException

from .auth.security import decode_access_token


def get_current_user(authorization: str = Header(None)) -> Dict[str, str]:
    """FastAPI dependency: the authenticated caller, or a 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header.")

    token = authorization[len("Bearer "):].strip()

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    user_id = payload.get("sub")
    if not user_id:
        # A token this server signed always has a subject; one without is not ours.
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    return {"id": str(user_id), "email": payload.get("email", "")}
