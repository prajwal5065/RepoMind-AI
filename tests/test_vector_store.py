import os
import shutil
import numpy as np
from core.vector_store import VectorStore
from core.embedder import Embedder
from models.response_models import CodeChunk, ChunkMetadata
from config import settings

def test_vector_store(monkeypatch):
    print("--- Testing FAISS Vector Store ---")
    session_id = "test_faiss_session"
    
    def mock_embed_chunks(self, chunks):
        return [(c, np.random.rand(3072).astype(np.float32)) for c in chunks]
    monkeypatch.setattr("core.embedder.Embedder.embed_chunks", mock_embed_chunks)
    
    # 1. Create 50 dummy chunks
    chunks = []
    for i in range(50):
        chunks.append(
            CodeChunk(
                metadata=ChunkMetadata(file_path=f"file_{i}.py", chunk_type="function", line_start=1, line_end=10),
                content=f"def function_{i}():\n    print('This is function {i}')"
            )
        )
        
    # Let's add a few specific semantic chunks to test search quality
    chunks.append(
        CodeChunk(
            metadata=ChunkMetadata(file_path="auth.py", chunk_type="function", line_start=1, line_end=5),
            content="def login(username, password):\n    # Verify user credentials from database\n    pass"
        )
    )
    chunks.append(
        CodeChunk(
            metadata=ChunkMetadata(file_path="utils.py", chunk_type="function", line_start=1, line_end=5),
            content="def get_database_connection():\n    # Connects to the postgres database\n    pass"
        )
    )
    
    # 2. Embed them
    print("Embedding 52 chunks...")
    embedder = Embedder()
    embedded_tuples = embedder.embed_chunks(chunks)
    embeddings = np.array([t[1] for t in embedded_tuples])
    
    # 3. Build index
    print("Building FAISS index...")
    vs = VectorStore()
    vs.build_index(chunks, embeddings)
    
    # 4. Save and Load
    print(f"Saving to {settings.FAISS_INDEX_PATH}/{session_id}...")
    vs.save_index(session_id)
    
    assert VectorStore.index_exists(session_id), "Index should exist after saving"
    
    print("Loading index from disk...")
    new_vs = VectorStore()
    loaded = new_vs.load_index(session_id)
    assert loaded, "Should be able to load index"
    assert new_vs.index.ntotal == 52, f"Expected 52 chunks, got {new_vs.index.ntotal}"
    
    # 5. Search test
    print("\nRunning queries...")
    
    queries = [
        "How to verify credentials?",
        "How to connect to postgres?",
        "Where is function 15?"
    ]
    
    for q in queries:
        print(f"\nQuery: '{q}'")
        q_emb = embedder.embed_query(q)
        results = new_vs.search(q_emb, top_k=2)
        
        for r in results:
            print(f"  -> File: {r.metadata.file_path} | Content preview: {r.content.splitlines()[0]}")
            
    print("\nVector Store tests passed!")
    
    # Cleanup
    shutil.rmtree(os.path.join(settings.FAISS_INDEX_PATH, session_id), ignore_errors=True)

if __name__ == "__main__":
    test_vector_store()
