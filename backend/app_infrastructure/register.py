import re
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError

from app_infrastructure.authentication import hash_password

PASSWORD_MIN_LENGTH = 8

def validate_password_strength(password: str) -> None:
    """SRS FR-1: minimum length + at least one number, enforced server-side."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number.")

def register_new_user(users_collection, name, email, password) -> dict:
    """Creates a new user document. Raises ValueError on any validation failure."""
    validate_password_strength(password)

    user_doc = {
        "name" : name.strip(),
        "email": email.strip().lower(),
        "password_hash": hash_password(password),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = users_collection.insert_one(user_doc)
    except DuplicateKeyError:
        raise ValueError("An account with this email already exists")

    return{"id": str(result.inserted_id), "name": user_doc["name"], "email": user_doc["email"]}
