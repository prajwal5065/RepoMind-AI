import os
import shutil
from typing import Dict, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from utils.logger import get_logger
from utils.file_utils import extract_zip, list_files
from core.repo_scanner import RepoScanner
from core.chunker import chunk_file
from models.response_models import ParseSummary, CodeChunk
from config import settings

logger = get_logger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# In-memory storage for chunks keyed by session_id
SESSION_CHUNKS: Dict[str, List[CodeChunk]] = {}

@router.post("/upload")
async def upload_repo(session_id: str = Form(...), file: UploadFile = File(...)):
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")

    # Validate file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds the 50MB limit")

    upload_dir = os.path.join(settings.UPLOAD_DIR, session_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    zip_path = os.path.join(upload_dir, file.filename)
    
    try:
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Saved uploaded zip to {zip_path}")
        
        extract_to = os.path.join(upload_dir, "extracted")
        extract_zip(zip_path, extract_to)
        
        files = list_files(extract_to)
        file_count = len(files)
        
        logger.info(f"Extracted {file_count} files for session {session_id}")
        
        return {
            "session_id": session_id,
            "file_count": file_count,
            "root_path": extract_to
        }
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during file processing")
    finally:
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass

@router.post("/parse/{session_id}", response_model=ParseSummary)
async def parse_repo(session_id: str):
    session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    
    if not os.path.exists(session_dir):
        logger.warning(f"Session directory not found: {session_dir}")
        raise HTTPException(status_code=404, detail="Session directory not found")

    try:
        # 1. Run RepoScanner
        scanner = RepoScanner(root_dir=session_dir)
        repo_map = scanner.scan()
        
        # 2. Run Chunker
        all_chunks = []
        for file in repo_map.files:
            file_path = os.path.join(session_dir, file)
            # Run chunker on each file
            chunks = chunk_file(file_path)
            logger.info(f"File {file} produced {len(chunks)} chunks")
            all_chunks.extend(chunks)
            
        # 3. Store in memory
        SESSION_CHUNKS[session_id] = all_chunks
        logger.info(f"Session {session_id} generated {len(all_chunks)} chunks from {len(repo_map.files)} files")
        
        # 4. Return summary
        return ParseSummary(
            total_files=len(repo_map.files),
            total_chunks=len(all_chunks),
            languages_detected=repo_map.detected_languages,
            frameworks_detected=repo_map.detected_frameworks
        )
    except Exception as e:
        logger.error(f"Error parsing repository for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during parsing")

