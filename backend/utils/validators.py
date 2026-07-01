"""
Centralised validation helpers.

All session_id and path checks go through this module so the rule is
defined exactly once and consistently applied across all endpoints.
"""
import os
import re
from fastapi import HTTPException

# session_id: alphanumeric, hyphens, underscores, 8-64 chars.
# This covers both UUID-style (upload) and git_<hex> (clone) patterns.
_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")


def validate_session_id(session_id: str) -> str:
    """
    Validate session_id format and return it unchanged.

    Raises HTTP 400 with a safe message if the format is invalid.
    Never includes the raw value in the error message to avoid
    reflecting attacker-controlled input.
    """
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format.",
        )
    return session_id


def safe_join(base_dir: str, *parts: str) -> str:
    """
    Join *parts* onto *base_dir* and verify the result stays inside
    *base_dir* (prevents path traversal).

    Returns the absolute resolved path.
    Raises HTTP 403 if the path escapes the base directory.
    """
    base = os.path.realpath(base_dir)
    target = os.path.realpath(os.path.join(base_dir, *parts))
    # Ensure target is inside base (add sep to avoid prefix confusion)
    if not (target == base or target.startswith(base + os.sep)):
        raise HTTPException(status_code=403, detail="Access denied.")
    return target
