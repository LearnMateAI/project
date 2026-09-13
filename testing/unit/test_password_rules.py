"""U-02 — server-side password rules (`app/auth/users.py`)."""

from unittest.mock import patch

import pytest
from pymongo.errors import DuplicateKeyError

from app.auth.security import MAX_PASSWORD_BYTES
from app.auth.users import register_new_user, validate_password_strength


def test_password_too_short():
    with pytest.raises(ValueError, match="at least"):
        validate_password_strength("Ab1")


def test_password_needs_a_number():
    with pytest.raises(ValueError, match="number"):
        validate_password_strength("PasswordOnly")


def test_strong_enough_password_passes():
    validate_password_strength("Password1")


def test_password_over_72_bytes_rejected():
    too_long = "A1" + ("x" * MAX_PASSWORD_BYTES)
    with pytest.raises(ValueError, match="at most"):
        validate_password_strength(too_long)


def test_register_rejects_blank_name():
    with pytest.raises(ValueError, match="Name is required"):
        register_new_user("   ", "a@b.co", "Password1")


def test_register_maps_duplicate_email():
    with patch("app.auth.users.user_store.create_user", side_effect=DuplicateKeyError("email")):
        with pytest.raises(ValueError, match="already exists"):
            register_new_user("Ada", "ada@example.com", "Password1")
