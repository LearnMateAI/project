"""I-01 — register / login / me HTTP contract (`app/routers/auth.py`)."""

from unittest.mock import patch

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.auth.security import hash_password
from testing.integration.app_factory import bearer, client

USER_OID = ObjectId("507f1f77bcf86cd799439011")


def _record(name="Ada", email="ada@uni.lk", password="Password1"):
    return {
        "_id": USER_OID,
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
    }


def test_register_201_returns_token_and_user():
    record = _record()
    with patch("app.auth.users.user_store.create_user", return_value=record), patch(
        "app.auth.users.user_store.public_view",
        return_value={"id": str(USER_OID), "name": "Ada", "email": "ada@uni.lk"},
    ):
        res = client().post(
            "/api/auth/register",
            json={"name": "Ada", "email": "ada@uni.lk", "password": "Password1"},
        )
    assert res.status_code == 201
    body = res.json()
    assert "token" in body and body["user"]["email"] == "ada@uni.lk"


def test_register_400_weak_password():
    res = client().post(
        "/api/auth/register",
        json={"name": "Ada", "email": "ada@uni.lk", "password": "short"},
    )
    assert res.status_code == 400
    assert "at least" in res.json()["detail"].lower() or "number" in res.json()["detail"].lower()


def test_register_409_duplicate_email():
    with patch(
        "app.auth.users.user_store.create_user",
        side_effect=DuplicateKeyError("email"),
    ):
        res = client().post(
            "/api/auth/register",
            json={"name": "Ada", "email": "ada@uni.lk", "password": "Password1"},
        )
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"]


def test_login_401_does_not_reveal_which_half_failed():
    with patch("app.auth.users.user_store.get_by_email", return_value=None):
        res = client().post(
            "/api/auth/login",
            json={"email": "nobody@uni.lk", "password": "Password1"},
        )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


def test_login_200_with_matching_password():
    record = _record()
    with patch("app.auth.users.user_store.get_by_email", return_value=record), patch(
        "app.auth.users.user_store.public_view",
        return_value={"id": str(USER_OID), "name": "Ada", "email": "ada@uni.lk"},
    ):
        res = client().post(
            "/api/auth/login",
            json={"email": "ada@uni.lk", "password": "Password1"},
        )
    assert res.status_code == 200
    assert "token" in res.json()


def test_me_401_without_bearer():
    res = client().get("/api/auth/me")
    assert res.status_code == 401


def test_me_200_with_valid_token():
    headers, user_id, email = bearer()
    res = client().get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == user_id
    assert res.json()["email"] == email
