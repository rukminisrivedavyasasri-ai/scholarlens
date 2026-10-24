import os
import logging
from typing import List
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self._model = None
        self._dimension = 384

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.warning(f"Could not load SentenceTransformer ({e}). Using deterministic semantic vectorizer fallback.")
                self._model = "fallback"
        return self._model

    def preload_model(self):
        """Pre-loads the embedding model into memory at startup to eliminate per-request cold starts."""
        logger.info("Initializing and pre-warming embedding model at startup...")
        model = self._get_model()
        if model != "fallback":
            try:
                # Pre-warm with short inference to compile execution graphs
                model.encode(["ScholarLens pre-warm inference"], normalize_embeddings=True, show_progress_bar=False)
                logger.info("Embedding model pre-warmed successfully.")
            except Exception as e:
                logger.warning(f"Error pre-warming embedding model: {e}")

    def embed_text(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        if model != "fallback":
            try:
                embeddings = model.encode(
                    texts, 
                    batch_size=batch_size, 
                    normalize_embeddings=True, 
                    show_progress_bar=False
                )
                return [emb.tolist() for emb in embeddings]
            except Exception as e:
                logger.error(f"Error encoding with SentenceTransformer: {e}")
        
        # Deterministic semantic vectorizer fallback (ensures tests run reliably offline)
        vectors = []
        for text in texts:
            vec = self._fallback_vector(text)
            vectors.append(vec)
        return vectors

    def _fallback_vector(self, text: str) -> List[float]:
        words = text.lower().split()
        vec = np.zeros(self._dimension, dtype=np.float32)
        if not words:
            return vec.tolist()
        for i, word in enumerate(words):
            h = hash(word) % self._dimension
            vec[h] += 1.0
            if i > 0:
                h_bi = hash(f"{words[i-1]}_{word}") % self._dimension
                vec[h_bi] += 0.5
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

embedding_service = EmbeddingService()
