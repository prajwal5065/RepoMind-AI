import os
import shutil
from typing import Dict, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from utils.logger import get_logger
from utils.file_utils import extract_zip, list_files
from core.repo_scanner import RepoScanner
from core.chunker import chunk_file
from core.vector_store import VectorStore
from core.embedder import Embedder
import time
from models.response_models import ParseSummary, CodeChunk, IndexSummary
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
async def parse_repo(session_id: str, background_tasks: BackgroundTasks):
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
        
        # 4. Trigger indexing in background
        background_tasks.add_task(index_repo, session_id)
        
        # 5. Return summary
        return ParseSummary(
            total_files=len(repo_map.files),
            total_chunks=len(all_chunks),
            languages_detected=repo_map.detected_languages,
            frameworks_detected=repo_map.detected_frameworks
        )
    except Exception as e:
        logger.error(f"Error parsing repository for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during parsing")

# Global lazy embedder
embedder_instance = None
def get_embedder():
    global embedder_instance
    if embedder_instance is None:
        embedder_instance = Embedder()
    return embedder_instance

@router.post("/index/{session_id}", response_model=IndexSummary)
async def index_repo(session_id: str):
    start_time = time.time()
    
    try:
        if VectorStore.index_exists(session_id):
            logger.info(f"Index for session {session_id} already exists. Skipping.")
            vs = VectorStore()
            vs.load_index(session_id)
            
            index_dir = os.path.join(settings.FAISS_INDEX_PATH, session_id)
            size_bytes = os.path.getsize(os.path.join(index_dir, "index.faiss")) + os.path.getsize(os.path.join(index_dir, "chunks.pkl"))
            
            return IndexSummary(
                indexed_chunks=len(vs.chunks),
                index_size_mb=round(size_bytes / (1024 * 1024), 2),
                time_taken_seconds=round(time.time() - start_time, 2)
            )
            
        chunks = SESSION_CHUNKS.get(session_id)
        if not chunks:
            raise HTTPException(status_code=400, detail="Chunks not found in memory. Call /parse first.")
            
        embedder = get_embedder()
        logger.info(f"Embedding {len(chunks)} chunks for session {session_id}...")
        embedded_tuples = embedder.embed_chunks(chunks)
        
        if not embedded_tuples:
            raise HTTPException(status_code=400, detail="No chunks to embed.")
            
        import numpy as np
        embeddings = np.array([t[1] for t in embedded_tuples])
        
        vs = VectorStore()
        vs.build_index(chunks, embeddings)
        vs.save_index(session_id)
        
        index_dir = os.path.join(settings.FAISS_INDEX_PATH, session_id)
        size_bytes = os.path.getsize(os.path.join(index_dir, "index.faiss")) + os.path.getsize(os.path.join(index_dir, "chunks.pkl"))
        
        return IndexSummary(
            indexed_chunks=len(chunks),
            index_size_mb=round(size_bytes / (1024 * 1024), 2),
            time_taken_seconds=round(time.time() - start_time, 2)
        )
    except Exception as e:
        logger.error(f"Error building index for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during indexing")

