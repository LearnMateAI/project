"""
The two cryptographic primitives the API depends on.

    bcrypt   turns a password into something safe to store
    JWT      turns a successful login into a token the client sends back

Deliberately small and free of policy: what counts as an acceptable password, and what
happens when a login fails, are decisions in users.py. This file only knows how to hash,
compare, sign and verify.

The secret is read from app.config at call time rather than captured at import, so
config.require_secret() at startup is the single place a missing secret is reported.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .. import config

# bcrypt hashes at most 72 bytes and silently ignores the rest, so a longer password would
# be no stronger than its first 72 bytes. Rejecting it is honest; truncating is not.
MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Hash a password for storage. The plaintext is never written anywhere."""
    return bcrypt.hashpw(
        plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check a login attempt against a stored hash.

    Returns False rather than raising on a malformed stored hash: a corrupt row should
    fail one login, not 500 the endpoint for everybody.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, email: str) -> str:
    """Issue a token that expires after JWT_EXPIRY_HOURS."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a token.

    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError, which deps.py turns into
    the two different 401 messages -- "log in again" and "invalid token" are different
    problems for the person reading them.
    """
    return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
