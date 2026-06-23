import numpy as np
from core.embedder import Embedder
from models.response_models import CodeChunk, ChunkMetadata

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def test_embedder():
    print("Initializing Embedder (this may take a moment to download the model)...")
    embedder = Embedder()
    
    # Create 5 dummy chunks
    chunks = [
        CodeChunk(
            metadata=ChunkMetadata(file_path="auth.py", chunk_type="function", line_start=1, line_end=5),
            content="# File: auth.py | Function: login\ndef login(username, password):\n    return verify_user(username, password)"
        ),
        CodeChunk(
            metadata=ChunkMetadata(file_path="auth.py", chunk_type="function", line_start=7, line_end=12),
            content="# File: auth.py | Function: verify_user\ndef verify_user(username, password):\n    db = get_db()\n    return db.check(username, password)"
        ),
        CodeChunk(
            metadata=ChunkMetadata(file_path="utils.py", chunk_type="function", line_start=1, line_end=3),
            content="# File: utils.py | Function: get_db\ndef get_db():\n    return DatabaseConnection()"
        ),
        CodeChunk(
            metadata=ChunkMetadata(file_path="ui.js", chunk_type="function", line_start=1, line_end=5),
            content="// File: ui.js | Function: renderButton\nfunction renderButton() {\n    return '<button>Click</button>';\n}"
        ),
        CodeChunk(
            metadata=ChunkMetadata(file_path="ui.css", chunk_type="module", line_start=1, line_end=3),
            content="/* File: ui.css */\nbutton {\n    color: red;\n}"
        )
    ]
    
    print("Embedding chunks...")
    embedded_chunks = embedder.embed_chunks(chunks)
    
    print("\n--- Cosine Similarities ---")
    
    # login vs verify_user (should be highly related)
    sim_auth = cosine_similarity(embedded_chunks[0][1], embedded_chunks[1][1])
    print(f"Similarity (login vs verify_user): {sim_auth:.4f}  (Expected > 0.7)")
    
    # verify_user vs get_db (should be related)
    sim_db = cosine_similarity(embedded_chunks[1][1], embedded_chunks[2][1])
    print(f"Similarity (verify_user vs get_db): {sim_db:.4f}")
    
    # login vs ui.js (should be low)
    sim_ui = cosine_similarity(embedded_chunks[0][1], embedded_chunks[3][1])
    print(f"Similarity (login vs ui.js): {sim_ui:.4f}  (Expected low)")
    
    # Test query
    q_emb = embedder.embed_query("How does the user authentication work?")
    sim_q = cosine_similarity(q_emb, embedded_chunks[0][1])
    print(f"\nSimilarity (Query vs login): {sim_q:.4f}")
    
    assert sim_auth > 0.65, f"Similarity between related code was too low: {sim_auth}"
    print("\nEmbedder tests completed successfully!")

if __name__ == "__main__":
    test_embedder()
