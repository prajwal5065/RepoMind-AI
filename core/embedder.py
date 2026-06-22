from typing import List, Tuple
import numpy as np
from models.response_models import CodeChunk
from utils.logger import get_logger

logger = get_logger(__name__)

class Embedder:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        logger.info(f"Loading embedding model: {model_name}")
        # Initialize the SentenceTransformer model (lazy import to prevent torch crash on missing VC++ redist)
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        
    def embed_chunks(self, chunks: List[CodeChunk]) -> List[Tuple[CodeChunk, np.ndarray]]:
        """
        Embeds a list of CodeChunks.
        Returns a list of tuples containing the original CodeChunk and its embedding.
        """
        if not chunks:
            return []
            
        # Extract the text content from the chunks
        texts = [chunk.content for chunk in chunks]
        
        # Encode the texts into embeddings
        # convert_to_numpy=True ensures we get numpy arrays back, which FAISS expects
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        
        # Pair each chunk with its corresponding embedding
        return list(zip(chunks, embeddings))
        
    def embed_query(self, question: str) -> np.ndarray:
        """
        Embeds a single search query string.
        Returns a 1D numpy array representing the query embedding.
        """
        # Encode the query and extract the single resulting vector
        embedding = self.model.encode([question], convert_to_numpy=True)[0]
        return embedding
