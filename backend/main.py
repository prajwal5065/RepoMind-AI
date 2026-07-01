from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import shutil
import asyncio
import time
from contextlib import asynccontextmanager
from utils.logger import get_logger
from api.upload import router as upload_router
from api.scanner import router as scanner_router
from api import upload, scanner, chat, analysis, docs, clone_repo
from utils.cache import cache
from config import settings

logger = get_logger(__name__)

async def cleanup_old_sessions():
    while True:
        await asyncio.sleep(3600)  # run every hour
        cutoff = time.time() - 86400  # 24h
        if not os.path.exists(settings.UPLOAD_DIR):
            continue
        for sid in os.listdir(settings.UPLOAD_DIR):
            path = os.path.join(settings.UPLOAD_DIR, sid)
            try:
                if os.path.getmtime(path) < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
                    shutil.rmtree(os.path.join(settings.FAISS_INDEX_PATH, sid), ignore_errors=True)
                    logger.info(f"Cleaned up old session: {sid}")
            except Exception as e:
                logger.error(f"Error cleaning up session {sid}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_old_sessions())
    yield
    task.cancel()

app = FastAPI(title="RepoMind-AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["Upload & Processing"])
app.include_router(scanner.router, prefix="/api", tags=["Repository Scanning"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis & Security"])
app.include_router(docs.router, prefix="/api", tags=["Documentation"])
app.include_router(clone_repo.router, prefix="/api", tags=["Upload & Processing"])

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "ok", "version": "1.0"}

@app.get("/api/cache-status/{session_id}", tags=["System"])
async def get_cache_status(session_id: str):
    return cache.status(session_id)

if __name__ == "__main__":
    logger.info("Starting FastAPI server")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
