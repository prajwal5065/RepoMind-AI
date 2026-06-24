import os
from models.response_models import RepoMap, CodeChunk, ChunkMetadata
from rag.retriever import Retriever

class MockEmbedder:
    def embed_query(self, question: str):
        return [0.1] * 384

class MockVectorStore:
    def __init__(self):
        self.chunks = []
    def load_index(self, session_id):
        return True
    def search(self, query_emb, top_k):
        # Return chunks exactly as provided to test ranking logic
        return self.chunks

def test_keyword_and_dependency_boost():
    print("--- Testing Retriever Ranking Logic ---")
    
    repo_map = RepoMap(
        root="/mock",
        modules=["auth", "utils", "db"],
        files=["auth.py", "utils.py", "db.py"],
        detected_languages=["Python"],
        detected_frameworks=[],
        dependencies={
            "auth.py": ["db.py"],
            "utils.py": []
        }
    )
    
    chunk1 = CodeChunk(
        metadata=ChunkMetadata(file_path="utils.py", chunk_type="function", function_name="helper", line_start=1, line_end=5),
        content="def helper(): pass"
    )
    chunk2 = CodeChunk(
        metadata=ChunkMetadata(file_path="auth.py", chunk_type="function", function_name="login", line_start=1, line_end=5),
        content="def login(): pass"
    )
    chunk3 = CodeChunk(
        metadata=ChunkMetadata(file_path="db.py", chunk_type="class", function_name="Database", line_start=1, line_end=5),
        content="class Database: pass"
    )
    
    import rag.retriever
    mock_vs = MockVectorStore()
    mock_vs.chunks = [chunk1, chunk2, chunk3]
    
    # Return only chunk1 and chunk2 from search, so chunk3 must be fetched via dependencies
    def mock_search(query_emb, top_k):
        return [chunk1, chunk2]
    mock_vs.search = mock_search
    
    original_vs = rag.retriever.VectorStore
    rag.retriever.VectorStore = lambda: mock_vs
    
    try:
        retriever = Retriever(MockEmbedder())
        
        # Query mentioning "login"
        # chunk2 (auth.py/login) should be boosted to top
        # chunk3 (db.py) is a dependency of auth.py, so it should be pulled in/boosted next
        results = retriever.retrieve("test_session", "How does login work?", repo_map, top_k=3)
        
        print("Results order:")
        for r in results:
            print(f" - {r.metadata.file_path} ({r.metadata.function_name})")
            
        assert results[0].metadata.function_name == "login", "Keyword boost failed"
        assert len(results) == 3, "Dependency chunk was not fetched"
        assert results[2].metadata.file_path == "db.py", "Dependency boost failed"
        
        print("\nRetriever Ranking tests passed!")
    finally:
        rag.retriever.VectorStore = original_vs

def test_is_overview_query():
    print("--- Testing Overview Query Classifier ---")
    assert Retriever.is_overview_query("What is this project?") == True
    assert Retriever.is_overview_query("Give me project details") == True
    assert Retriever.is_overview_query("Explain this repository") == True
    assert Retriever.is_overview_query("What does this repo do?") == True
    assert Retriever.is_overview_query("Repository overview") == True
    assert Retriever.is_overview_query("Project summary") == True
    assert Retriever.is_overview_query("Explain system design") == True
    assert Retriever.is_overview_query("How does auth work?") == False
    assert Retriever.is_overview_query("Fix the bug in login") == False
    print("Overview Query Classifier tests passed!\n")

def test_retrieve_overview():
    print("--- Testing Retriever Overview Logic ---")
    
    repo_map = RepoMap(
        root="/mock",
        modules=["auth", "utils", "db"],
        files=["auth.py", "utils.py", "db.py", "README.md", "main.py"],
        detected_languages=["Python"],
        detected_frameworks=[],
        dependencies={},
        entry_points=["main.py"]
    )
    
    chunk_readme = CodeChunk(
        metadata=ChunkMetadata(file_path="README.md", chunk_type="text_block", line_start=1, line_end=10),
        content="# Project Title"
    )
    chunk_main = CodeChunk(
        metadata=ChunkMetadata(file_path="main.py", chunk_type="module", line_start=1, line_end=5),
        content="import os"
    )
    chunk_auth = CodeChunk(
        metadata=ChunkMetadata(file_path="auth.py", chunk_type="function", line_start=1, line_end=5),
        content="def login(): pass"
    )
    chunk_env = CodeChunk(
        metadata=ChunkMetadata(file_path=".env.example", chunk_type="text_block", line_start=1, line_end=5),
        content="VAR=1"
    )
    
    import rag.retriever
    mock_vs = MockVectorStore()
    mock_vs.chunks = [chunk_readme, chunk_main, chunk_auth, chunk_env]
    
    # FAISS returns .env and auth.py as semantic matches
    def mock_search(query_emb, top_k):
        return [chunk_env, chunk_auth]
    mock_vs.search = mock_search
    
    original_vs = rag.retriever.VectorStore
    rag.retriever.VectorStore = lambda: mock_vs
    
    try:
        retriever = Retriever(MockEmbedder())
        results = retriever.retrieve_overview("test_session", "What is this project?", repo_map, top_k=5)
        
        print("Results order:")
        for r in results:
            print(f" - {r.metadata.file_path}")
            
        # Should prioritize README and entry point (main.py), followed by FAISS
        assert results[0].metadata.file_path == "README.md", "Did not fetch README"
        assert results[1].metadata.file_path == "main.py", "Did not fetch entry point"
        assert len(results) == 4, "Should have 4 unique chunks"
        
        print("Retriever Overview tests passed!\n")
    finally:
        rag.retriever.VectorStore = original_vs

if __name__ == "__main__":
    test_keyword_and_dependency_boost()
    test_is_overview_query()
    test_retrieve_overview()
