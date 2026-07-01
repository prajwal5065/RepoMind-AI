"""
Security tests for RepoMind-AI backend.

Covers every vulnerability addressed in the Security Audit (Task 1):
  1. Zip Slip — crafted zip with path-traversal entry
  2. session_id validation — invalid formats rejected with 400
  3. Path traversal in /file/ endpoint — 403
  4. Authentication — missing / wrong key → 401
  5. Stack trace not leaked in 500 responses
  6. CORS — wildcard is not configured; correct origin passes

Run with:
    cd backend
    pytest ../tests/test_security.py -v
"""
import io
import os
import zipfile
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App import — adjust sys.path so imports resolve from backend/
# ---------------------------------------------------------------------------
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Patch settings before the app is imported so we control secrets.
with patch.dict(
    os.environ,
    {
        "API_KEY": "test-secret-key-1234",
        "ALLOWED_ORIGINS": "http://localhost:3000",
        "GEMINI_API_KEY": "fake",
        "GROQ_API_KEY": "fake",
        "DEBUG": "true",
    },
):
    from main import app  # noqa: E402

VALID_KEY = "test-secret-key-1234"
WRONG_KEY = "wrong-key"
AUTH_HEADERS = {"X-API-Key": VALID_KEY}

client = TestClient(app, raise_server_exceptions=False)


# ============================================================================
# 1. Zip Slip
# ============================================================================
class TestZipSlip:
    """extract_zip must block members whose path escapes the target directory."""

    def _make_zip_with_traversal(self) -> bytes:
        """Create an in-memory zip with a path-traversal filename."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../evil.txt", "malicious content")
        buf.seek(0)
        return buf.read()

    def test_zip_slip_raises_value_error(self, tmp_path):
        from utils.file_utils import extract_zip

        zip_path = tmp_path / "evil.zip"
        zip_path.write_bytes(self._make_zip_with_traversal())

        with pytest.raises(ValueError, match="Zip Slip blocked"):
            extract_zip(str(zip_path), str(tmp_path / "extract"))

    def test_safe_zip_extracts_normally(self, tmp_path):
        from utils.file_utils import extract_zip

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("src/main.py", "print('hello')")
        buf.seek(0)
        zip_path = tmp_path / "safe.zip"
        zip_path.write_bytes(buf.read())

        extract_dir = tmp_path / "extract"
        extract_zip(str(zip_path), str(extract_dir))
        assert (extract_dir / "src" / "main.py").exists()

    def test_upload_endpoint_rejects_zip_slip(self, tmp_path):
        """The /api/upload endpoint must return 400 for a zip-slip archive."""
        zip_bytes = self._make_zip_with_traversal()
        response = client.post(
            "/api/upload",
            data={"session_id": "abcd1234efgh"},
            files={"file": ("repo.zip", zip_bytes, "application/zip")},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 400


# ============================================================================
# 2. session_id Validation
# ============================================================================
class TestSessionIdValidation:
    """Every endpoint with a session_id path param must reject malformed IDs."""

    INVALID_IDS = [
        "../../../etc/passwd",   # path traversal
        "../../secret",          # path traversal variant
        "ab",                    # too short (< 8 chars)
        "a" * 65,                # too long (> 64 chars)
        "has spaces here",       # spaces not allowed
        "has;semicolon",         # special chars
        "<script>xss</script>",  # XSS attempt
    ]

    @pytest.mark.parametrize("sid", INVALID_IDS)
    def test_parse_rejects_invalid_session_id(self, sid):
        resp = client.post(f"/api/parse/{sid}", headers=AUTH_HEADERS)
        assert resp.status_code == 400, f"Expected 400 for session_id={sid!r}"

    @pytest.mark.parametrize("sid", INVALID_IDS)
    def test_index_rejects_invalid_session_id(self, sid):
        resp = client.post(f"/api/index/{sid}", headers=AUTH_HEADERS)
        assert resp.status_code == 400, f"Expected 400 for session_id={sid!r}"

    @pytest.mark.parametrize("sid", INVALID_IDS)
    def test_analyze_rejects_invalid_session_id(self, sid):
        resp = client.get(f"/api/analyze/{sid}", headers=AUTH_HEADERS)
        assert resp.status_code == 400, f"Expected 400 for session_id={sid!r}"

    @pytest.mark.parametrize("sid", INVALID_IDS)
    def test_repo_map_rejects_invalid_session_id(self, sid):
        resp = client.get(f"/api/repo-map/{sid}", headers=AUTH_HEADERS)
        assert resp.status_code == 400, f"Expected 400 for session_id={sid!r}"

    def test_valid_session_id_passes_validation(self):
        """A valid session_id should not be rejected at the validation stage."""
        from utils.validators import validate_session_id
        # Should not raise
        assert validate_session_id("git_abcdef123456") == "git_abcdef123456"
        assert validate_session_id("a" * 8) == "a" * 8
        assert validate_session_id("a" * 64) == "a" * 64


# ============================================================================
# 3. Path Traversal
# ============================================================================
class TestPathTraversal:
    """safe_join must block attempts to escape the base directory."""

    def test_safe_join_blocks_traversal(self, tmp_path):
        from utils.validators import safe_join
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            safe_join(str(tmp_path), "../../etc/passwd")
        assert exc_info.value.status_code == 403

    def test_safe_join_allows_valid_path(self, tmp_path):
        from utils.validators import safe_join

        result = safe_join(str(tmp_path), "subdir", "file.py")
        assert result.startswith(str(tmp_path))

    def test_file_endpoint_blocks_traversal(self):
        """GET /api/file/{session_id}?path=../../etc/passwd must return 400 or 403."""
        resp = client.get(
            "/api/file/abcd1234efgh",
            params={"path": "../../etc/passwd"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code in (400, 403, 404)


# ============================================================================
# 4. Authentication
# ============================================================================
class TestAuthentication:
    """All non-/health endpoints must require a valid X-API-Key header."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/repo-map/abcd1234efgh"),
        ("GET", "/api/analyze/abcd1234efgh"),
        ("POST", "/api/parse/abcd1234efgh"),
        ("POST", "/api/index/abcd1234efgh"),
        ("POST", "/api/docs/abcd1234efgh"),
        ("GET", "/api/cache-status/abcd1234efgh"),
    ]

    @pytest.mark.parametrize("method, url", PROTECTED_ENDPOINTS)
    def test_missing_api_key_returns_401(self, method, url):
        resp = client.request(method, url)
        assert resp.status_code == 401, f"Expected 401 for {method} {url}"

    @pytest.mark.parametrize("method, url", PROTECTED_ENDPOINTS)
    def test_wrong_api_key_returns_401(self, method, url):
        resp = client.request(method, url, headers={"X-API-Key": WRONG_KEY})
        assert resp.status_code == 401, f"Expected 401 for {method} {url} with wrong key"

    def test_health_is_public(self):
        """GET /health must be accessible without any credentials."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_correct_key_is_accepted(self):
        """A request with the correct key must pass auth (may fail later for other reasons)."""
        resp = client.get("/api/repo-map/abcd1234efgh", headers=AUTH_HEADERS)
        # Should not be 401 — could be 404 (session not found) which is fine
        assert resp.status_code != 401


# ============================================================================
# 5. Stack Trace Not Leaked
# ============================================================================
class TestNoStackTraceLeak:
    """5xx responses must never include Python tracebacks in the body."""

    TRACEBACK_MARKERS = [
        "Traceback (most recent call last)",
        "File \"/",
        "raise ",
        "Exception(",
    ]

    def test_analysis_500_hides_traceback(self):
        """If analysis raises an unexpected error the response body must be clean."""
        with patch(
            "api.analysis.StaticAnalyzer.analyze_repo",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.get("/api/analyze/abcd1234efgh", headers=AUTH_HEADERS)

        body = resp.text
        for marker in self.TRACEBACK_MARKERS:
            assert marker not in body, f"Traceback marker found in response: {marker!r}"

    def test_global_handler_hides_traceback(self):
        """Unhandled exceptions caught by the global handler must not leak details."""
        @app.get("/test-error-leak")
        async def _raise():
            raise RuntimeError("secret internal detail")

        resp = client.get("/test-error-leak")
        assert "secret internal detail" not in resp.text
        assert "RuntimeError" not in resp.text


# ============================================================================
# 6. CORS
# ============================================================================
class TestCORS:
    """CORS must only allow explicitly configured origins."""

    def test_allowed_origin_gets_acao_header(self):
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_disallowed_origin_gets_no_acao_header(self):
        resp = client.get(
            "/health",
            headers={"Origin": "https://evil.com"},
        )
        # FastAPI/Starlette omits the ACAO header for non-allowed origins
        assert resp.headers.get("access-control-allow-origin") != "https://evil.com"
