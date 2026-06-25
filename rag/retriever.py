import os
from typing import List
from models.response_models import CodeChunk, RepoMap
from core.vector_store import VectorStore
from core.embedder import Embedder
from utils.logger import get_logger

logger = get_logger(__name__)

FILE_PRIORITY = {
    'main.py': 10, 'app.py': 10,
    'api/': 8, 'core/': 8, 'rag/': 8, 'analysis/': 7,
    'models/': 5, 'utils/': 4,
    '.env.example': -20, '.gitignore': -20,
    'README': -5, # README is useful but not code
}

class Retriever:
    def __init__(self, embedder: Embedder):
        self.embedder = embedder

    @staticmethod
    def is_overview_query(query: str) -> bool:
        OVERVIEW_KEYWORDS = [
            'what is this', 'what does this', 'explain this repo',
            'explain the repo', 'explain this project', 'what is the project',
            'project overview', 'repo overview', 'repository overview', 'give me an overview',
            'what does this codebase', 'project details', 'project summary', 'project purpose',
            'repo structure', 'repository structure', 'folder structure',
            'project tree', 'show files', 'list files', 'architecture', 'explain system design',
            'how is this structured', 'what are the main components',
        ]
        q_lower = query.lower()
        return any(kw in q_lower for kw in OVERVIEW_KEYWORDS)

    def retrieve(self, session_id: str, question: str, repo_map: RepoMap, top_k: int = 7) -> List[CodeChunk]:
        vs = VectorStore()
        if not vs.load_index(session_id):
            logger.warning(f"Could not load index for session {session_id}")
            return []
            
        # Step 1 & 2: Embed the question and fetch top 15 candidates
        query_embedding = self.embedder.embed_query(question)
        candidates = vs.search(query_embedding, top_k=15)
        
        if not candidates:
            return []
            
        # Step 3: Keyword Boost
        q_lower = question.lower()
        
        scored_candidates = []
        for i, chunk in enumerate(candidates):
            score = 15 - i # base semantic score
            
            for pattern, weight in FILE_PRIORITY.items():
                if pattern in chunk.metadata.file_path:
                    score += weight
                    break
            
            # Boost if file name mentioned
            file_name = os.path.basename(chunk.metadata.file_path).lower()
            file_name_no_ext = os.path.splitext(file_name)[0]
            
            if file_name in q_lower or file_name_no_ext in q_lower:
                score += 10
                
            # Boost if function/class name mentioned
            if chunk.metadata.function_name and chunk.metadata.function_name.lower() in q_lower:
                score += 10
                
            scored_candidates.append((score, chunk))
            
        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        reranked_chunks = [c[1] for c in scored_candidates]
        
        # Step 4: Dependency Fetch
        top_result = reranked_chunks[0]
        top_file = top_result.metadata.file_path
        
        related_files = set()
        # Find files that import the top_file
        for f_path, deps in repo_map.dependencies.items():
            if top_file in deps:
                related_files.add(f_path)
        # Also include files the top_file imports
        if top_file in repo_map.dependencies:
            for dep in repo_map.dependencies[top_file]:
                related_files.add(dep)
                
        # We find chunks in vs.chunks that belong to related_files
        dependency_chunks = []
        for chunk in vs.chunks:
            if chunk.metadata.file_path in related_files:
                dependency_chunks.append(chunk)
                
        # Deduplicate and append dependency chunks to reranked list
        existing_ids = {f"{c.metadata.file_path}:{c.metadata.line_start}" for c in reranked_chunks}
        
        for dc in dependency_chunks:
            dc_id = f"{dc.metadata.file_path}:{dc.metadata.line_start}"
            if dc_id not in existing_ids:
                # We append them at the end, or we could insert them. 
                # Since we just want them available, appending is fine.
                reranked_chunks.append(dc)
                existing_ids.add(dc_id)
                
        # Step 5: Return top 7 chunks
        return reranked_chunks[:top_k]

    def retrieve_overview(self, session_id: str, question: str, repo_map: RepoMap, top_k: int = 5) -> List[CodeChunk]:
        """Special retrieval logic for overview queries: Force includes README and entry points."""
        vs = VectorStore()
        if not vs.load_index(session_id):
            return []
            
        overview_chunks = []
        existing_ids = set()
        
        # 1. Fetch README and Entry Points
        for chunk in vs.chunks:
            fpath = chunk.metadata.file_path
            if fpath.lower() == 'readme.md' or fpath in repo_map.entry_points:
                chunk_id = f"{fpath}:{chunk.metadata.line_start}"
                if chunk_id not in existing_ids:
                    overview_chunks.append(chunk)
                    existing_ids.add(chunk_id)
                    
        # 2. Add FAISS semantic matches
        query_embedding = self.embedder.embed_query(question)
        candidates = vs.search(query_embedding, top_k=top_k)
        
        for chunk in candidates:
            chunk_id = f"{chunk.metadata.file_path}:{chunk.metadata.line_start}"
            if chunk_id not in existing_ids:
                overview_chunks.append(chunk)
                existing_ids.add(chunk_id)
                
        return overview_chunks[:top_k]
