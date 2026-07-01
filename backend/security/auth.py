"""
API Key authentication dependency.

Every protected endpoint must declare:
    Depends(verify_api_key)

The key is read from the ``API_KEY`` environment variable (via Settings).
Requests that omit or supply a wrong key receive HTTP 401.

The /health endpoint is intentionally excluded from auth so monitoring
tools can probe the service without credentials.
"""
import secrets
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from config import settings

# FastAPI extracts the value from the X-API-Key header automatically.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(_api_key_header)) -> None:
    """
    FastAPI dependency: validate the X-API-Key header.

    Raises HTTP 401 if the key is missing or incorrect.
    Uses ``secrets.compare_digest`` to prevent timing attacks.
    """
    if not settings.API_KEY:
        # If the operator forgot to set API_KEY the server should refuse all
        # requests rather than become an open relay.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is not configured for authenticated access. Set API_KEY.",
        )

    provided = api_key or ""
    if not secrets.compare_digest(provided, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
