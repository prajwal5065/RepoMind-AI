from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
from core.llm_client import LLMClient
from rag.retriever import Retriever
from api.upload import get_embedder
from core.repo_scanner import RepoScanner
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    session_id: str
    question: str

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    session_dir = os.path.join(settings.UPLOAD_DIR, request.session_id, "extracted")
    if not os.path.exists(session_dir):
        logger.warning(f"Session directory not found: {session_dir}")
        raise HTTPException(status_code=404, detail="Session not found")
        
    try:
        # Load repo map (fast scan)
        scanner = RepoScanner(session_dir)
        repo_map = scanner.scan()
        
        embedder = get_embedder()
        retriever = Retriever(embedder)
        
        # 1. Retrieve chunks
        context_chunks = retriever.retrieve(request.session_id, request.question, repo_map, top_k=7)
        
        if not context_chunks:
            raise HTTPException(status_code=400, detail="No indexed chunks found for this session. Please index the repo first.")
            
        # 2. Build LLM client
        llm = LLMClient()
        
        # 3. Return StreamingResponse
        return StreamingResponse(
            llm.answer_stream(request.question, context_chunks, repo_map),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint for session {request.session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during chat generation")
