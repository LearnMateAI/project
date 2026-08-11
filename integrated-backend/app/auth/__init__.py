"""
Accounts: who is calling, and whether they are who they say.

    security.py  the primitives -- bcrypt hashing, JWT issue and decode
    users.py     the policy -- password rules, registration, login

Split that way because the two change for different reasons. Raising the minimum password
length is a policy change; moving off bcrypt is not.

Storage lives in learnmate/storage/users.py, which never sees a plaintext password and has
no opinion about what makes one acceptable.
"""

from .security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from .users import authenticate_user, register_new_user, validate_password_strength

__all__ = [
    "authenticate_user",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "register_new_user",
    "validate_password_strength",
    "verify_password",
]
