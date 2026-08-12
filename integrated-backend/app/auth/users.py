"""
Registration and login: the rules, as opposed to the cryptography.

Two functions, and the difference in how they fail is the point:

    register_new_user   raises ValueError with a message the user should read and act on
    authenticate_user   returns None, saying nothing about which half was wrong

The asymmetry is deliberate. A registration form has to say "your password needs a number"
or it cannot be completed. A login form that says "no account with that address" tells an
attacker which addresses are worth guessing passwords for, so it says only that the
combination was wrong.
"""

from typing import Dict, Optional

from pymongo.errors import DuplicateKeyError

from learnmate.storage import users as user_store

from .. import config
from .security import MAX_PASSWORD_BYTES, hash_password, verify_password


def validate_password_strength(password: str) -> None:
    """Server-side password rules. Raises ValueError naming the one that failed."""
    password = password or ""

    if len(password) < config.PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters long.")
    if not any(character.isdigit() for character in password):
        raise ValueError("Password must contain at least one number.")
    # Rejected rather than truncated: bcrypt ignores everything past 72 bytes, so a longer
    # password would be silently weaker than the user believes it to be.
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes long.")


def register_new_user(name: str, email: str, password: str) -> Dict:
    """
    Create an account and return its public view.

    Raises ValueError on a weak password, an empty name, or an address already
    registered -- the router maps that last one to 409 and the rest to 400.
    """
    if not (name or "").strip():
        raise ValueError("Name is required.")

    validate_password_strength(password)

    try:
        user = user_store.create_user(name, email, hash_password(password))
    except DuplicateKeyError:
        # Caught rather than pre-checked: two simultaneous registrations of the same
        # address would both pass a lookup, and only the unique index can actually decide.
        raise ValueError("An account with this email already exists.")

    return user_store.public_view(user)


def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """
    Check a login. Returns the user's public view, or None.

    Both failure paths return the same None so the caller cannot accidentally reveal
    which one happened.
    """
    user = user_store.get_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None
    return user_store.public_view(user)
