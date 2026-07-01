# Security Audit Report — RepoMind-AI

> **Audit date:** 2026-07-01  
> **Scope:** FastAPI backend (`backend/`)  
> **Standard:** [OWASP Top 10 (2021)](https://owasp.org/Top10/)

---

## OWASP Top 10 Checklist

| # | Category | Status | Notes |
|---|---|---|---|
| A01 | Broken Access Control | ✅ Fixed | API key auth added to all endpoints; /health intentionally public |
| A02 | Cryptographic Failures | ✅ Fixed | Secrets read from env vars; no plaintext secrets in code; timing-safe compare |
| A03 | Injection | ✅ Fixed | Zip Slip blocked; session_id sanitised; subprocess uses list args (no shell=True) |
| A04 | Insecure Design | ✅ Fixed | CORS restricted; /docs disabled in production; non-root Docker user |
| A05 | Security Misconfiguration | ✅ Fixed | Pinned deps; .dockerignore prevents .env in image; DEBUG=false by default |
| A06 | Vulnerable Components | ✅ Fixed | All deps pinned with `==`; dev tools separated from production deps |
| A07 | Auth & Identity Failures | ✅ Fixed | API key required on all data endpoints; timing-safe key comparison |
| A08 | Software Integrity Failures | ⚠️ Partial | Deps pinned; add `pip-audit` to CI to automate CVE scanning |
| A09 | Security Logging & Monitoring | ✅ Fixed | Structured JSON logging; full tracebacks server-side; LOG_LEVEL configurable |
| A10 | Server-Side Request Forgery | ✅ Existing | SSRF mitigated in clone_repo.py via URL allowlist and BLOCKED_HOSTS regex |

---

## Vulnerability Details

### 🔴 CVE-Class: Zip Slip (CWE-22)

**File:** `backend/utils/file_utils.py`

**Before (vulnerable):**
```python
with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_to)   # no path validation
```

**After (fixed):**
```python
for member in zf.infolist():
    target = os.path.realpath(os.path.join(extract_root, member.filename))
    if not (target == extract_root or target.startswith(extract_root + os.sep)):
        raise ValueError(f"Zip Slip blocked: '{member.filename}'")
    zf.extract(member, extract_root)
```

**Explanation:** A crafted zip archive can contain entries with filenames like `../../etc/passwd`. When `extractall()` is called without validation, these entries are written to arbitrary locations on the filesystem. The fix resolves each member's full path and rejects anything that escapes the extraction directory.

---

### 🔴 Stack Trace Leak (CWE-209)

**File:** `backend/api/analysis.py`

**Before (vulnerable):**
```python
except Exception as e:
    error_details = traceback.format_exc()
    with open("analysis_error.txt", "w") as f:   # writes traceback to disk
        f.write(error_details)
    raise HTTPException(status_code=500, detail=error_details)  # leaks to client!
```

**After (fixed):**
```python
except Exception:
    logger.error(f"Analysis failed:\n{traceback.format_exc()}")  # server-side only
    raise HTTPException(status_code=500, detail="Internal server error during analysis.")
```

**Explanation:** Returning raw Python tracebacks in API responses reveals implementation details, file paths, library versions, and sometimes credentials. The fix logs the full traceback server-side and returns only a generic message to the client.

---

### 🔴 CORS Wildcard with Credentials (CWE-942)

**File:** `backend/main.py`

**Before (vulnerable):**
```python
allow_origins=["*"],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
```

**After (fixed):**
```python
_allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
allow_origins=_allowed_origins,          # explicit allowlist from env
allow_methods=["GET", "POST", "DELETE"], # minimum required
allow_headers=["Content-Type", "X-API-Key", "X-LLM-Provider"],
```

---

### 🔴 No Authentication (CWE-306)

**Files:** All routers

All endpoints were completely open. Now `X-API-Key` header required on all data endpoints via `Depends(verify_api_key)`. Key is read from `API_KEY` env var. Comparison uses `secrets.compare_digest` to prevent timing-based oracle attacks.

**Frontend integration:** Add `X-API-Key: <your-key>` to all API calls. Store as `NEXT_PUBLIC_API_KEY` in `.env.local`.

---

### 🟠 Missing session_id Validation (CWE-22, CWE-20)

Centralised `validate_session_id()` in `utils/validators.py` enforces `^[a-zA-Z0-9_-]{8,64}$` before any filesystem operation. `safe_join()` uses `os.path.realpath` for reliable traversal detection in the file endpoint.

---

### 🟠 Unpinned Dependencies (CWE-1395)

All packages now pinned with `==`. Dev tools removed from production requirements.

**Next step — add to CI:**
```bash
pip install pip-audit && pip-audit -r backend/requirements.txt
```

---

### 🟡 Placeholder API Key in Config (CWE-798)

`GEMINI_API_KEY` default `"your_gemini_api_key_here"` removed. All keys default to `""`. The auth module detects an empty `API_KEY` and returns HTTP 503.

---

### 🟡 Dockerfile: .env Baked Into Image

`.dockerignore` now excludes `.env`, `venv/`, `data/`. Dockerfile runs as non-root `appuser`.

---

## Remaining Recommendations

| Priority | Action |
|---|---|
| 🟠 High | Add `pip-audit` to GitHub Actions CI for automated CVE scanning |
| 🟠 High | Add security response headers (`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`) |
| 🟡 Medium | Rate-limit `/api/upload` and `/api/clone-repo` (currently only `/api/chat` is rate-limited) |
| 🟡 Medium | Add request body size limits at the nginx/uvicorn level |
| 🟢 Low | Replace API key with short-lived JWT if multi-user support is added |
