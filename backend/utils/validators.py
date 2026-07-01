"""
Centralised validation helpers.

All session_id and path checks go through this module so the rule is
defined exactly once and consistently applied across all endpoints.

Usage
-----
**As a FastAPI path-param dependency (preferred):**

    from typing import Annotated
    from fastapi import Depends
    from utils.validators import valid_session_id

    @router.get("/resource/{session_id}")
    def handler(session_id: Annotated[str, Depends(valid_session_id)]):
        ...   # session_id is already validated here

FastAPI resolves the dependency *before* the handler is called, so a
malformed session_id is rejected with HTTP 400 at the routing layer —
no per-function guard needed.
"""
import os
import re
from typing import Annotated

from fastapi import Depends, HTTPException

# session_id: alphanumeric, hyphens, underscores, 8–64 chars.
# Covers both UUID-style (upload) and git_<hex12> (clone) patterns.
_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")


def valid_session_id(session_id: str) -> str:
    """
    FastAPI dependency: validate a session_id path parameter.

    Bind to a path param with ``Annotated[str, Depends(valid_session_id)]``
    so FastAPI validates before the handler body executes.

    Raises HTTP 400 with a generic message — never echoes the raw value
    back to the caller (avoids reflecting attacker-controlled input).
    """
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format.",
        )
    return session_id


# Convenience alias for use in ``Annotated`` type hints.
ValidSessionId = Annotated[str, Depends(valid_session_id)]


def safe_join(base_dir: str, *parts: str) -> str:
    """
    Join *parts* onto *base_dir* and verify the result stays inside
    *base_dir* (prevents path traversal / directory escape).

    Both *base_dir* and the joined result are resolved with
    ``os.path.realpath`` so symlinks and ``..`` components are
    fully expanded before comparison.

    The ``+ os.sep`` guard prevents the prefix-confusion attack where
    a legitimate base ``/data/uploads/session_abc`` would incorrectly
    match a sibling directory ``/data/uploads/session_abcXXX`` under a
    plain ``startswith`` check without the separator.

    Returns the absolute resolved path.
    Raises HTTP 403 if the path escapes the base directory.
    """
    base = os.path.realpath(base_dir)
    target = os.path.realpath(os.path.join(base_dir, *parts))

    # target must equal base exactly OR be strictly inside it.
    # Adding os.sep ensures "/data/session_abc" cannot prefix-match
    # "/data/session_abcXXX".
    if not (target == base or target.startswith(base + os.sep)):
        raise HTTPException(status_code=403, detail="Access denied.")
    return target
