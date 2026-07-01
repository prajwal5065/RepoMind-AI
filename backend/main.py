"""
FastAPI application entry point.

Security features applied here
--------------------------------
- CORS restricted to ALLOWED_ORIGINS (env-configurable, defaults to localhost).
- Global exception handler prevents stack traces reaching API consumers.
- /health is intentionally public for uptime monitoring.
- All other routes are protected via X-API-Key (see security/auth.py).
"""
import asyncio
import os
import shutil
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from config import settings
from utils.cache import cache
from utils.logger import get_logger
from security.auth import verify_api_key
from api import upload, scanner, chat, analysis, docs, clone_repo

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Background cleanup task
# ---------------------------------------------------------------------------
async def cleanup_old_sessions() -> None:
    """Remove upload directories and FAISS indexes older than 24 hours."""
    while True:
        await asyncio.sleep(3600)  # run every hour
        cutoff = time.time() - 86400  # 24 h
        if not os.path.exists(settings.UPLOAD_DIR):
            continue
        for sid in os.listdir(settings.UPLOAD_DIR):
            path = os.path.join(settings.UPLOAD_DIR, sid)
            try:
                if os.path.getmtime(path) < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
                    shutil.rmtree(
                        os.path.join(settings.FAISS_INDEX_PATH, sid),
                        ignore_errors=True,
                    )
                    logger.info(f"Cleaned up old session: {sid}")
            except Exception as e:
                logger.error(f"Error cleaning up session {sid}: {e}")


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_old_sessions())
    logger.info("RepoMind-AI backend started.")
    yield
    task.cancel()
    logger.info("RepoMind-AI backend shutting down.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="RepoMind-AI",
    version="1.0.0",
    lifespan=lifespan,
    # Disable automatic /docs and /redoc in production to reduce attack surface.
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


# ---------------------------------------------------------------------------
# CORS — restricted to configured origins, not wildcard
# ---------------------------------------------------------------------------
_allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "X-LLM-Provider"],
)


# ---------------------------------------------------------------------------
# Global exception handler — never leak internal details to clients
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback server-side only.
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}:\n"
        f"{traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(upload.router, prefix="/api", tags=["Upload & Processing"])
app.include_router(scanner.router, prefix="/api", tags=["Repository Scanning"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis & Security"])
app.include_router(docs.router, prefix="/api", tags=["Documentation"])
app.include_router(clone_repo.router, prefix="/api", tags=["Upload & Processing"])


# ---------------------------------------------------------------------------
# Public endpoints (no auth)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    """Public health probe — no authentication required."""
    return {"status": "ok", "version": "1.0"}


# ---------------------------------------------------------------------------
# Protected system endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/api/cache-status/{session_id}",
    tags=["System"],
    dependencies=[Depends(verify_api_key)],
)
async def get_cache_status(session_id: str):
    return cache.status(session_id)


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting FastAPI server")
    uvicorn.run(
        "main:app",
        host="127.0.0.1",   # bind to loopback only in dev; use a proxy in prod
        port=8000,
        reload=True,
    )
