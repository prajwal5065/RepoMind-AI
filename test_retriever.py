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

if __name__ == "__main__":
    test_keyword_and_dependency_boost()
