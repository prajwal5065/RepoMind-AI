from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from utils.logger import get_logger
from api.upload import router as upload_router
from api.scanner import router as scanner_router
from api import upload, scanner, chat, analysis, docs
from utils.cache import cache

logger = get_logger(__name__)

app = FastAPI(title="RepoMind-AI", version="1.0.0")

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
