import os
from fastapi import APIRouter, Depends, HTTPException
from core.repo_scanner import RepoScanner
from models.response_models import RepoMap
from config import settings
from utils.logger import get_logger
from utils.validators import ValidSessionId, safe_join
from security.auth import verify_api_key

logger = get_logger(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])

@router.get("/repo-map/{session_id}", response_model=RepoMap)
def get_repo_map(session_id: ValidSessionId):
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

@router.get("/dependencies/{session_id}")
def get_dependencies(session_id: ValidSessionId):
    """Returns the dependency graph for a given session."""

    session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    
    if not os.path.exists(session_dir):
        logger.warning(f"Session directory not found: {session_dir}")
        raise HTTPException(status_code=404, detail="Session or extracted repository not found")

    try:
        scanner = RepoScanner(root_dir=session_dir)
        repo_map = scanner.scan()
        return repo_map.dependencies
    except Exception as e:
        logger.error(f"Error building dependency graph for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/file/{session_id}")
def get_file_content(session_id: ValidSessionId, path: str):
    session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    # safe_join resolves realpath and enforces the + os.sep guard — 403 on escape
    file_path = safe_join(session_dir, path)
        
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Could not read file")
