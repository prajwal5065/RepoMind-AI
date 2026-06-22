import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from utils.logger import get_logger
from utils.file_utils import extract_zip, list_files
from config import settings

logger = get_logger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

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
