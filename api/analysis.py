import os
import re
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from analysis.static_analyzer import StaticAnalyzer
from analysis.security_scanner import SecurityScanner
from core.llm_client import LLMClient
from core.repo_scanner import RepoScanner
from models.response_models import Finding
from config import settings
from utils.cache import cache

router = APIRouter()
llm_client = LLMClient()

@router.get("/analyze/{session_id}", response_model=List[Finding])
async def analyze_repository(session_id: str):
    if not re.match(r'^[\w-]+$', session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    cache_key = f"{session_id}:analysis"
    cached_findings = cache.get(cache_key)
    if cached_findings is not None:
        return cached_findings

    session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    if not os.path.exists(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    # Run Static Analysis
    static_analyzer = StaticAnalyzer(session_dir)
    static_findings = await run_in_threadpool(static_analyzer.analyze_repo, session_id)

    # Run Security Scans
    security_scanner = SecurityScanner(session_dir)
    security_findings = await run_in_threadpool(security_scanner.analyze_repo)

    all_findings = static_findings + security_findings

    # Get Repo Map for LLM Context
    repo_map_key = f"{session_id}:repo_map"
    repo_map = cache.get(repo_map_key)
    if not repo_map:
        scanner = RepoScanner(session_dir)
        repo_map = await run_in_threadpool(scanner.scan)
        cache.set(repo_map_key, repo_map)

    # Use LLM to explain HIGH severity issues and 1-line for MEDIUM/LOW
    if all_findings:
        all_findings = await llm_client.explain_findings(all_findings, repo_map)

    cache.set(cache_key, all_findings)
    return all_findings
