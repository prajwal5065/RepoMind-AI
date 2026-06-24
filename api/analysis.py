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
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()
llm_client = LLMClient()

@router.get("/analyze/{session_id}", response_model=List[Finding])
async def analyze_repository(session_id: str):
    logger.info(f"Analysis request received for session: {session_id}")
    try:
        if not re.match(r'^[\w-]+$', session_id):
            logger.error("Invalid session ID format")
            raise HTTPException(status_code=400, detail="Invalid session ID format")
        
        cache_key = f"{session_id}:analysis"
        cached_findings = cache.get(cache_key)
        if cached_findings is not None:
            logger.info("Returning cached analysis results")
            return cached_findings

        session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
        if not os.path.exists(session_dir):
            logger.error(f"Session directory not found: {session_dir}")
            raise HTTPException(status_code=404, detail="Session does not exist or repository has not been parsed")

        # Run Static Analysis
        logger.info("Static analysis started")
        static_analyzer = StaticAnalyzer(session_dir)
        static_findings = await run_in_threadpool(static_analyzer.analyze_repo, session_id)
        logger.info(f"Static analysis completed. Found {len(static_findings)} issues.")

        # Run Security Scans
        logger.info("Security scan started")
        security_scanner = SecurityScanner(session_dir)
        security_findings = await run_in_threadpool(security_scanner.analyze_repo)
        logger.info(f"Security scan completed. Found {len(security_findings)} issues.")

        all_findings = static_findings + security_findings

        # Get Repo Map for LLM Context
        repo_map_key = f"{session_id}:repo_map"
        repo_map = cache.get(repo_map_key)
        if not repo_map:
            scanner = RepoScanner(session_dir)
            repo_map = await run_in_threadpool(scanner.scan)
            cache.set(repo_map_key, repo_map)

        # Use LLM to explain HIGH severity issues and 1-line for MEDIUM/LOW
        logger.info("LLM explanation started")
        if all_findings:
            all_findings = await llm_client.explain_findings(all_findings, repo_map)
        logger.info("LLM explanation completed")

        cache.set(cache_key, all_findings)
        logger.info("Response returned")
        return all_findings
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        with open("analysis_error.txt", "w") as f:
            f.write(error_details)
        logger.error(f"Analysis failed: {error_details}")
        raise HTTPException(status_code=500, detail=error_details)
