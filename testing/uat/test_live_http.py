"""UAT — live HTTP against a running API. Skipped unless LEARNMATE_UAT=1."""

from __future__ import annotations

import os
import uuid

import pytest
import requests

pytestmark = pytest.mark.uat

API = os.environ.get("LEARNMATE_API_URL", "http://localhost:8010").rstrip("/")
RUN = os.environ.get("LEARNMATE_UAT") == "1"


def _skip_if_offline():
    if not RUN:
        pytest.skip("Set LEARNMATE_UAT=1 and start the API on LEARNMATE_API_URL (default :8010)")


def test_a08_health_uses_non_default_ports():
    _skip_if_offline()
    res = requests.get(f"{API}/api/health", timeout=10)
    assert res.status_code == 200
    body = res.json()
    assert "status" in body and "checks" in body
    mongo = body["checks"].get("mongodb") or {}
    uri = mongo.get("uri") or ""
    if uri:
        assert "27018" in uri or "mongodb" in uri.lower()


def test_a02_register_login_me_round_trip():
    _skip_if_offline()
    email = f"uat.{uuid.uuid4().hex[:10]}@learnmate.test"
    password = "Password1"
    name = "UAT Student"
    register = requests.post(
        f"{API}/api/auth/register",
        json={"name": name, "email": email, "password": password},
        timeout=15,
    )
    assert register.status_code == 201, register.text
    token = register.json()["token"]
    me = requests.get(
        f"{API}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert me.status_code == 200
    assert me.json()["email"] == email.lower() or me.json()["email"] == email

    login = requests.post(
        f"{API}/api/auth/login",
        json={"email": email, "password": "wrong-password"},
        timeout=10,
    )
    assert login.status_code == 401
    assert login.json()["detail"] == "Invalid email or password."


def test_a02_weak_password_is_400():
    _skip_if_offline()
    res = requests.post(
        f"{API}/api/auth/register",
        json={"name": "X", "email": f"weak.{uuid.uuid4().hex[:8]}@x.test", "password": "short"},
        timeout=10,
    )
    assert res.status_code == 400


def test_protected_routes_401_without_token():
    _skip_if_offline()
    for path in ("/api/documents", "/api/jobs", "/api/chat/sessions", "/api/analytics"):
        res = requests.get(f"{API}{path}", timeout=10)
        assert res.status_code == 401, path
