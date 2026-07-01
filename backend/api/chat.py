from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
import os
import time
from core.llm_client import LLMClient
from rag.retriever import Retriever
from api.upload import get_embedder
from core.repo_scanner import RepoScanner
from config import settings
from utils.logger import get_logger
from utils.validators import validate_session_id
from security.auth import verify_api_key

logger = get_logger(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self.clients: dict = {}

    def __call__(self, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        self.clients.setdefault(client_ip, [])
        # Evict old timestamps
        self.clients[client_ip] = [t for t in self.clients[client_ip] if now - t < self.window]
        if len(self.clients[client_ip]) >= self.requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
        self.clients[client_ip].append(now)


rate_limiter = RateLimiter(requests=20, window=60)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider: str = ""   # "grok" | "gemini" | "" (uses server default)


# ---------------------------------------------------------------------------
# Helpers (sync — to be called via run_in_threadpool)
# ---------------------------------------------------------------------------
def _load_context(session_id: str, message: str, is_overview: bool):
    """
    Synchronous: scan repo, embed query, retrieve top-k chunks.
    Returns (context_chunks, repo_map, readme_chunk) or raises RuntimeError.
    """
    session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    if not os.path.exists(session_dir):
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    # Use cache to avoid scanning the repo directory repeatedly
    from utils.cache import cache
    repo_map_key = f"{session_id}:repo_map"
    repo_map = cache.get(repo_map_key)
    if not repo_map:
        scanner = RepoScanner(session_dir)
        repo_map = scanner.scan()
        cache.set(repo_map_key, repo_map)

    if is_overview:
        from core.vector_store import VectorStore
        vs = VectorStore()
        readme_chunk = None
        if vs.load_index(session_id):
            readme_chunk = next((c for c in vs.chunks if 'readme.md' in c.metadata.file_path.lower()), None)
        return [], repo_map, readme_chunk

    embedder = get_embedder()
    retriever = Retriever(embedder)
    
    context_chunks = retriever.retrieve(session_id, message, repo_map, top_k=7)

    return context_chunks, repo_map, None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post(
    "/chat",
    dependencies=[Depends(rate_limiter)],
    summary="Chat with the repository (streaming)",
    description=(
        "Ask a question about the indexed repository. "
        "Responses stream as plain text (text/event-stream). "
        "A **Sources Cited** section is appended at the end listing the files used.\n\n"
        "**Prerequisites:** the session must have been uploaded/cloned, parsed, and indexed first.\n\n"
        "**Rate limit:** 20 requests per minute per IP."
    ),
    tags=["Chat"],
)
async def chat_endpoint(request: ChatRequest):
    # ── Step 0: validate session_id from the request body ───────────────
    validate_session_id(request.session_id)

    # ── Step 1: validate session exists ──────────────────────────────────
    session_dir = os.path.join(settings.UPLOAD_DIR, request.session_id, "extracted")
    if not os.path.exists(session_dir):
        logger.warning(f"Session directory not found: {session_dir}")
        raise HTTPException(status_code=404, detail="Session not found. Upload or clone a repository first.")

    is_overview = Retriever.is_overview_query(request.message)

    # ── Step 2: retrieve context in a thread (blocking I/O + CPU) ────────
    try:
        context_chunks, repo_map, readme_chunk = await run_in_threadpool(
            _load_context, request.session_id, request.message, is_overview
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Context loading failed for session {request.session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load repository context.")

    if not is_overview and not context_chunks:
        raise HTTPException(
            status_code=400,
            detail="No indexed chunks found. Run /parse and /index on this session first."
        )

    # ── Step 3: stream the LLM answer ────────────────────────────────────
    llm = LLMClient(provider=request.provider or None)

    async def generate():
        try:
            if is_overview:
                async for token in llm.answer_overview_stream(request.message, repo_map, readme_chunk):
                    yield token
            else:
                async for token in llm.answer_stream(request.message, context_chunks, repo_map, session_id=request.session_id):
                    yield token
        except Exception as e:
            logger.error(f"Streaming error for session {request.session_id}: {e}")
            yield "\n\n*Error: stream interrupted. Please try again.*"

    return StreamingResponse(
        generate(),
        media_type="text/plain",      # plain text — easier to consume with fetch ReadableStream
        headers={
            "X-Accel-Buffering": "no",   # disable nginx buffering if behind a proxy
            "Cache-Control": "no-cache",
        }
    )
