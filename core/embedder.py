from typing import List, Tuple
import numpy as np
from google import genai
from models.response_models import CodeChunk
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Gemini's modern embedding model: 3072-dimensional.
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 3072

class Embedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        logger.info(f"Initialising Gemini embedder: {model_name}")
        self.model_name = model_name
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Call the Gemini Embeddings API for a batch of texts.
        Returns a float32 numpy array of shape (len(texts), EMBEDDING_DIM).
        """
        all_embeddings = []
        batch_size = 100  # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            # Replace newlines — often a best practice for embeddings
            batch = [t.replace("\n", " ") for t in batch]
            try:
                # The modern genai client takes the model name directly
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=batch,
                    config={"task_type": "RETRIEVAL_DOCUMENT"}
                )
                
                # Extract embeddings
                batch_embeddings = [item.values for item in response.embeddings]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Error calling Gemini embedding API: {e}")
                all_embeddings.extend([[0.0] * EMBEDDING_DIM] * len(batch))
                
        return np.array(all_embeddings, dtype=np.float32)

    def embed_chunks(self, chunks: List[CodeChunk]) -> List[Tuple[CodeChunk, np.ndarray]]:
        """
        Embeds a list of CodeChunks.
        Returns a list of (CodeChunk, embedding_vector) tuples.
        """
        if not chunks:
            return []

        texts = [chunk.content for chunk in chunks]
        embeddings = self._embed_texts(texts)
        return list(zip(chunks, embeddings))

    def embed_query(self, question: str) -> np.ndarray:
        """
        Embeds a single query string.
        Returns a 1-D float32 numpy array of length EMBEDDING_DIM.
        """
        try:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=question,
                config={"task_type": "RETRIEVAL_QUERY"}
            )
            return np.array(response.embeddings[0].values, dtype=np.float32)
        except Exception as e:
            logger.error(f"Error calling Gemini embedding API for query: {e}")
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)
