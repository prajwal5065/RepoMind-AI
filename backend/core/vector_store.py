import os
import faiss
import numpy as np
import pickle
from typing import List, Tuple
from models.response_models import CodeChunk
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class VectorStore:
    def __init__(self, embedding_dim: int = 3072):
        self.embedding_dim = embedding_dim
        # IndexFlatIP uses Inner Product (equivalent to Cosine Similarity when vectors are normalized)
        self.index = faiss.IndexFlatIP(embedding_dim)
        self.chunks: List[CodeChunk] = []
        
    def build_index(self, chunks: List[CodeChunk], embeddings: np.ndarray):
        if len(chunks) == 0 or len(embeddings) == 0:
            logger.warning("No chunks or embeddings provided to build_index")
            return
            
        # Ensure embeddings are normalized for inner product to be equivalent to cosine similarity
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        self.chunks = chunks
        logger.info(f"Built FAISS index with {self.index.ntotal} vectors.")
        
    def search(self, query_embedding: np.ndarray, top_k: int = 7) -> List[CodeChunk]:
        if self.index.ntotal == 0:
            return []
            
        # Normalize the query embedding for cosine similarity
        query_embedding = np.array([query_embedding])
        faiss.normalize_L2(query_embedding)
        
        distances, indices = self.index.search(query_embedding, top_k)
        
        results = []
        # Return chunks matching the indices
        for idx in indices[0]:
            if idx != -1 and idx < len(self.chunks):
                results.append(self.chunks[idx])
                
        return results

    def save_index(self, session_id: str):
        index_dir = os.path.join(settings.FAISS_INDEX_PATH, session_id)
        os.makedirs(index_dir, exist_ok=True)
        
        index_path = os.path.join(index_dir, "index.faiss")
        chunks_path = os.path.join(index_dir, "chunks.pkl")
        
        faiss.write_index(self.index, index_path)
        with open(chunks_path, 'wb') as f:
            pickle.dump(self.chunks, f)
            
        logger.info(f"Saved FAISS index for session {session_id}")

    def load_index(self, session_id: str) -> bool:
        index_dir = os.path.join(settings.FAISS_INDEX_PATH, session_id)
        index_path = os.path.join(index_dir, "index.faiss")
        chunks_path = os.path.join(index_dir, "chunks.pkl")
        
        if not os.path.exists(index_path) or not os.path.exists(chunks_path):
            return False
            
        try:
            loaded_index = faiss.read_index(index_path)
            if loaded_index.d != self.embedding_dim:
                logger.warning(f"Dimension mismatch for {session_id}: expected {self.embedding_dim}, got {loaded_index.d}. Index needs rebuilding.")
                return False
            self.index = loaded_index
            with open(chunks_path, 'rb') as f:
                self.chunks = pickle.load(f)
            logger.info(f"Loaded FAISS index for session {session_id} with {self.index.ntotal} vectors")
            return True
        except Exception as e:
            logger.error(f"Failed to load FAISS index for {session_id}: {e}")
            return False

    @staticmethod
    def index_exists(session_id: str) -> bool:
        index_dir = os.path.join(settings.FAISS_INDEX_PATH, session_id)
        index_path = os.path.join(index_dir, "index.faiss")
        chunks_path = os.path.join(index_dir, "chunks.pkl")
        return os.path.exists(index_path) and os.path.exists(chunks_path)
