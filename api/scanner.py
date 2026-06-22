import os
from fastapi import APIRouter, HTTPException
from core.repo_scanner import RepoScanner
from models.response_models import RepoMap
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.get("/repo-map/{session_id}", response_model=RepoMap)
async def get_repo_map(session_id: str):
    """Returns the RepoMap for a given session."""
    session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    
    if not os.path.exists(session_dir):
        logger.warning(f"Session directory not found: {session_dir}")
        raise HTTPException(status_code=404, detail="Session or extracted repository not found")

    try:
        scanner = RepoScanner(root_dir=session_dir)
        repo_map = scanner.scan()
        return repo_map
    except Exception as e:
        logger.error(f"Error scanning repository for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during repository scanning")
