"""I-05 — CORS allowlist and the root discovery document."""

from app import config
from testing.integration.app_factory import client


def test_root_points_at_health_and_docs():
    res = client().get("/")
    assert res.status_code == 200
    body = res.json()
    assert body["health"] == "/api/health"
    assert body["docs"] == "/docs"


def test_cors_allows_configured_frontend_origin():
    origin = config.FRONTEND_ORIGINS[0]
    res = client().options(
        "/api/auth/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.headers.get("access-control-allow-origin") == origin


def test_default_origin_is_vite_dev_server():
    assert "http://localhost:5173" in config.FRONTEND_ORIGINS
