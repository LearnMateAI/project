"""U-14 — frontend source contracts (no browser). Paths the UI must keep calling."""

from pathlib import Path


def test_error_message_uses_backend_detail_and_network_hint(frontend_root: Path):
    src = (frontend_root / "src" / "api" / "client.js").read_text(encoding="utf-8")
    assert "error?.response?.data?.detail" in src
    assert "ERR_NETWORK" in src
    assert "Cannot reach the server" in src
    assert "localStorage.removeItem(\"token\")" in src
    assert "window.location.replace(\"/login\")" in src


def test_auth_api_paths(frontend_root: Path):
    auth_src = (frontend_root / "src" / "api" / "auth.js").read_text(encoding="utf-8")
    client_src = (frontend_root / "src" / "api" / "client.js").read_text(encoding="utf-8")
    assert 'baseURL: import.meta.env.VITE_API_BASE_URL || "/api"' in client_src
    assert 'api.post("/auth/register"' in auth_src
    assert 'api.post("/auth/login"' in auth_src
    assert 'api.get("/auth/me"' in auth_src


def test_jobs_poll_and_terminal_states(frontend_root: Path):
    src = (frontend_root / "src" / "api" / "jobs.js").read_text(encoding="utf-8")
    assert "/api/jobs/" in src
    assert 'job.status === "done"' in src
    assert 'job.status === "failed"' in src
    assert "FAST_POLL_MS" in src


def test_app_routes_explore_vs_protected(frontend_root: Path):
    src = (frontend_root / "src" / "App.jsx").read_text(encoding="utf-8")
    for path in ("/login", "/register", "/dashboard", "/documents", "/chat", "/resources"):
        assert path in src
    assert 'path="/"' in src
    assert "ProtectedRoute" in src
    assert 'Navigate to="/"' in src or 'to="/"' in src


def test_upload_client_enforces_ten_megabytes(frontend_root: Path):
    src = (frontend_root / "src" / "components" / "DocumentsCard.jsx").read_text(encoding="utf-8")
    assert "const MAX_MB = 10" in src
    assert "Only PDF files are accepted" in src


def test_protected_route_waits_while_checking(frontend_root: Path):
    src = (frontend_root / "src" / "components" / "ProtectedRoute.jsx").read_text(encoding="utf-8")
    assert "checking" in src
    assert 'to="/login"' in src
