"""
Verifying tokens issued by Keycloak instead of by this backend.

Mirrors security.py's role: this file only knows how to verify a token. Deciding what to
do with a verified one -- find or create a local user -- lives in users.py's Keycloak
functions, the same split as security.py vs users.py for the original login path.

A token from this server is signed with a secret only this server holds (HS256). A token
from Keycloak is signed with Keycloak's own *private* key, so the only way to check it is
to ask Keycloak's public endpoint what its current public keys are (a JWKS) and verify the
signature against those instead. PyJWKClient does that fetch and caches the result, rather
than hitting Keycloak on every single request.
"""

from typing import Dict

import jwt
from jwt import PyJWKClient

from .. import config

_JWKS_CLIENT: PyJWKClient = None


def _jwks_client() -> PyJWKClient:
    # Built once and reused: fetching the key set on every request would mean a Keycloak
    # round trip for every API call this backend ever serves.
    global _JWKS_CLIENT
    if _JWKS_CLIENT is None:
        _JWKS_CLIENT = PyJWKClient(config.KEYCLOAK_JWKS_URL)
    return _JWKS_CLIENT


def decode_keycloak_token(token: str) -> Dict:
    """
    Verify a Keycloak-issued token and return its claims.

    Raises the same jwt exceptions as decode_access_token, so deps.py can catch both
    kinds of token with one pair of except clauses.

    Audience verification is switched off deliberately, not omitted by oversight: this
    realm's default token carries aud="account" (Keycloak's own built-in audience) rather
    than this app's client id, because no audience mapper has been configured for
    learnmate-frontend. Signature and issuer are still checked -- what verify_aud would
    add on top is confirming the token was intended *for this specific client*, which
    matters more once several clients share one realm. Flagged here as a real
    simplification, not a silent gap.
    """
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token, signing_key.key, algorithms=["RS256"],
        issuer=config.KEYCLOAK_ISSUER,
        options={"verify_aud": False},
    )
