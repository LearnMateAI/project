from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from database.db import check_connection
from api.routes import router as auth_router
from api.documents import router as documents_router

load_dotenv()

app = FastAPI(title="LearnMateAI Backend")
app.include_router(documents_router)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "LearnMateAI Backend",
        "health": "/api/health",
    }

@app.get("/api/health")
def health_check():
    db_ok = check_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }
