from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from utils.logger import get_logger
from api.upload import router as upload_router

logger = get_logger(__name__)

app = FastAPI(title="RepoMind-AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api")

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "ok", "version": "1.0"}

if __name__ == "__main__":
    logger.info("Starting FastAPI server")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
