import os
import re
import uuid
import shutil
import subprocess
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from config import settings
from utils.logger import get_logger
from utils.cache import cache
from security.auth import verify_api_key

logger = get_logger(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])

# Allowed URL patterns — only HTTPS public Git hosts.
# This regex explicitly blocks local paths, file://, ssh://, git://, etc.
ALLOWED_URL_PATTERN = re.compile(
    r'^https://(github\.com|gitlab\.com|bitbucket\.org|[\w\-][\w\-\.]*\.[\w]{2,})'
    r'/([\w\-\.]+/[\w\-\.]+?)(?:\.git)?/?$',
    re.IGNORECASE
)

# Block private IP ranges and localhost to prevent SSRF
BLOCKED_HOSTS = re.compile(
    r'^(localhost|127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|0\.0\.0\.0)',
    re.IGNORECASE
)

MAX_REPO_SIZE_MB = 200  # Block repos larger than 200MB after clone
CLONE_TIMEOUT_SECONDS = 120


class CloneRequest(BaseModel):
    repo_url: str


class CloneResponse(BaseModel):
    session_id: str
    repo_name: str
    status: str
    file_count: int


def _validate_url(url: str) -> str:
    """
    Validate the repository URL and return the normalized URL.
    Raises HTTPException for any invalid/unsafe URL.
    """
    url = url.strip()

    if not url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Only HTTPS repository URLs are supported (e.g., https://github.com/user/repo)."
        )

    match = ALLOWED_URL_PATTERN.match(url)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository URL. Supported formats: https://github.com/user/repo or https://gitlab.com/user/repo"
        )

    host = match.group(1)
    if BLOCKED_HOSTS.match(host):
        raise HTTPException(status_code=400, detail="Private/local network URLs are not allowed.")

    # Derive repo_name from URL (last path segment without .git)
    repo_name = match.group(2).rstrip("/").split("/")[-1].replace(".git", "")
    return url, repo_name


def _get_dir_size_mb(path: str) -> float:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total / (1024 * 1024)


def _clone(repo_url: str, extract_to: str) -> None:
    """
    Perform the actual git clone using subprocess with a strict argument list
    (no shell=True) to completely prevent command injection.
    """
    os.makedirs(extract_to, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "git", "clone",
                "--depth", "1",          # Shallow clone — only latest commit
                "--single-branch",        # Only default branch
                "--no-tags",              # Skip tags to save bandwidth
                repo_url,
                extract_to
            ],
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT_SECONDS,
            shell=False,                 # CRITICAL: shell=False prevents injection
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error(f"git clone failed: {stderr}")

            # Provide friendly messages for common failures
            if "Repository not found" in stderr or "not found" in stderr.lower():
                raise RuntimeError("Repository not found. Check the URL and ensure it is public.")
            elif "Authentication" in stderr or "could not read Username" in stderr:
                raise RuntimeError("Authentication failed. Only public repositories are supported.")
            elif "early EOF" in stderr or "Connection" in stderr:
                raise RuntimeError("Network error while cloning. Please try again.")
            else:
                raise RuntimeError(f"Clone failed: {stderr[:300]}")

        # Remove the .git directory — we only need the source files for analysis.
        # Keeping it causes the scanner to walk into binary pack files and hooks.
        git_dir = os.path.join(extract_to, ".git")
        if os.path.isdir(git_dir):
            shutil.rmtree(git_dir, ignore_errors=True)
            logger.info(f"Removed .git directory from {extract_to}")

    except subprocess.TimeoutExpired:
        shutil.rmtree(extract_to, ignore_errors=True)
        raise RuntimeError(
            f"Clone timed out after {CLONE_TIMEOUT_SECONDS}s. The repository may be too large or unreachable."
        )


def _count_files(path: str) -> int:
    count = 0
    for _, _, files in os.walk(path):
        count += len(files)
    return count


@router.post(
    "/clone-repo",
    response_model=CloneResponse,
    summary="Clone a public Git repository",
    description=(
        "Clone a public GitHub, GitLab, or Bitbucket repository by URL.\n\n"
        "The repository is shallow-cloned (depth=1) and stored under a unique session_id. "
        "Once cloned, use `/api/parse/{session_id}` and `/api/index/{session_id}` to continue the pipeline.\n\n"
        "**Supported URL formats:**\n"
        "- `https://github.com/user/repo`\n"
        "- `https://github.com/user/repo.git`\n"
        "- `https://gitlab.com/user/repo`\n"
        "- `https://bitbucket.org/user/repo`\n\n"
        "**Constraints:**\n"
        "- Only public repositories are supported.\n"
        "- Maximum cloned size: 200 MB.\n"
        f"- Clone timeout: {CLONE_TIMEOUT_SECONDS} seconds.\n"
    ),
    tags=["Upload & Processing"],
)
async def clone_repo(request: CloneRequest):
    """
    Clone a public Git repository into a unique session directory.
    Returns the session_id to use for subsequent parse/index/chat calls.
    """
    repo_url, repo_name = _validate_url(request.repo_url)

    session_id = f"git_{uuid.uuid4().hex[:12]}"
    extract_to = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")

    logger.info(f"Cloning {repo_url} -> session {session_id}")

    try:
        await run_in_threadpool(_clone, repo_url, extract_to)
    except RuntimeError as e:
        # Clean up any partial clone
        shutil.rmtree(os.path.join(settings.UPLOAD_DIR, session_id), ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        shutil.rmtree(os.path.join(settings.UPLOAD_DIR, session_id), ignore_errors=True)
        logger.error(f"Unexpected error during clone: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during repository cloning.")

    # Check size after clone
    size_mb = await run_in_threadpool(_get_dir_size_mb, extract_to)
    if size_mb > MAX_REPO_SIZE_MB:
        shutil.rmtree(os.path.join(settings.UPLOAD_DIR, session_id), ignore_errors=True)
        raise HTTPException(
            status_code=413,
            detail=f"Repository is too large ({size_mb:.0f} MB). Maximum allowed size is {MAX_REPO_SIZE_MB} MB."
        )

    file_count = await run_in_threadpool(_count_files, extract_to)
    cache.invalidate_session(session_id)

    logger.info(f"Clone complete: session={session_id}, files={file_count}, size={size_mb:.1f}MB")

    return CloneResponse(
        session_id=session_id,
        repo_name=repo_name,
        status="cloned",
        file_count=file_count,
    )
