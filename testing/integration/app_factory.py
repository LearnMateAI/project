"""Slim FastAPI app: same routers, no lifespan, no GGUF, no Docker."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app import config
from app.auth.security import create_access_token
from app.errors import register_error_handlers
from app.routers import analytics
from app.routers import auth
from app.routers import chat
from app.routers import documents
from app.routers import jobs
from app.routers import resources


def build_slim_app() -> FastAPI:
    app = FastAPI(title="LearnMate test")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.FRONTEND_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(resources.router)
    app.include_router(chat.router)
    app.include_router(jobs.router)
    app.include_router(analytics.router)

    @app.get("/")
    def root():
        return {"name": "LearnMate API", "health": "/api/health", "docs": "/docs"}

    return app


def client() -> TestClient:
    return TestClient(build_slim_app(), raise_server_exceptions=False)


def bearer(user_id: str = "507f1f77bcf86cd799439011", email: str = "student@example.com"):
    token = create_access_token(user_id, email)
    return {"Authorization": f"Bearer {token}"}, user_id, email
