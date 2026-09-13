"""U-01 — bcrypt hashing and JWT sign/verify (`app/auth/security.py`)."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import config
from app.auth.security import (
    MAX_PASSWORD_BYTES,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("CorrectHorse1")
    assert hashed != "CorrectHorse1"
    assert hashed.startswith("$2")
    assert verify_password("CorrectHorse1", hashed) is True


def test_wrong_password_does_not_verify():
    hashed = hash_password("CorrectHorse1")
    assert verify_password("WrongHorse1", hashed) is False


def test_corrupt_stored_hash_returns_false_not_raise():
    assert verify_password("anything1", "not-a-bcrypt-hash") is False


def test_access_token_round_trip():
    token = create_access_token("507f1f77bcf86cd799439011", "student@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "507f1f77bcf86cd799439011"
    assert payload["email"] == "student@example.com"
    assert "exp" in payload and "iat" in payload


def test_tampered_token_is_rejected():
    token = create_access_token("abc", "a@b.co")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token + "x")


def test_expired_token_is_rejected(monkeypatch):
    payload = {
        "sub": "abc",
        "email": "a@b.co",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_max_password_bytes_is_bcrypt_limit():
    assert MAX_PASSWORD_BYTES == 72
