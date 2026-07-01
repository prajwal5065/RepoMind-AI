import os
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from core.repo_scanner import RepoScanner
from core.llm_client import LLMClient
from core.doc_generator import DocGenerator
from utils.cache import cache
from config import settings
from models.response_models import ProjectDoc

router = APIRouter()
llm_client = LLMClient()
doc_generator = DocGenerator(llm_client)

@router.post("/docs/{session_id}", response_model=ProjectDoc)
async def generate_docs(session_id: str):
    if not re.match(r'^[\w-]+$', session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")

    cache_key = f"{session_id}:docs"
    cached_docs = cache.get(cache_key)
    if cached_docs:
        return cached_docs

    session_dir = os.path.join(settings.UPLOAD_DIR, session_id, "extracted")
    if not os.path.exists(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    # Generate repo map (we should ideally cache this too)
    repo_map_key = f"{session_id}:repo_map"
    repo_map = cache.get(repo_map_key)
    if not repo_map:
        scanner = RepoScanner(session_dir)
        repo_map = scanner.scan()
        cache.set(repo_map_key, repo_map)

    # Generate project level docs
    project_doc = await doc_generator.generate_project_docs(repo_map)

    # Generate module level docs
    # Only iterate up to 5 modules to avoid massive API limits on large repos
    for mod in repo_map.modules[:5]:
        mod_files = [f for f in repo_map.files if f.startswith(mod)]
        if mod_files:
            mod_doc = await doc_generator.generate_module_docs(mod, mod_files)
            project_doc.modules.append(mod_doc)

    cache.set(cache_key, project_doc)
    return project_doc

@router.get("/docs/{session_id}/export", response_class=PlainTextResponse)
async def export_docs(session_id: str):
    cache_key = f"{session_id}:docs"
    cached_docs = cache.get(cache_key)
    if not cached_docs:
        raise HTTPException(status_code=404, detail="Docs not found. Generate them first.")
    
    # Format as markdown
    doc = cached_docs
    md = f"# Project Documentation\\n\\n## Tech Stack\\n{doc.tech_stack}\\n\\n## Architecture Summary\\n{doc.architecture_summary}\\n\\n"
    md += "## Entry Points\\n"
    for ep in doc.entry_points:
        md += f"- `{ep}`\\n"
    
    md += "\\n## Modules\\n"
    for mod in doc.modules:
        md += f"### {mod.module_path}\\n"
        md += f"**Purpose**: {mod.purpose}\\n\\n"
        md += "**Dependencies**: " + ", ".join(mod.dependencies) + "\\n\\n"
        md += "**Public Functions**:\\n"
        for fn in mod.public_functions:
            md += f"- `{fn.get('name', 'unknown')}`: {fn.get('description', '')}\\n"
        md += "\\n"
    
    return md
