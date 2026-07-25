from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingGenerator:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initializes the embedding model. 
        all-MiniLM-L6-v2 is fast, lightweight, and perfect for standard RAG tasks.
        """
        print(f"[*] Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.vector_size = self.model.get_embedding_dimension()

    def embed_chunks(self, texts: list[str]) -> np.ndarray:
        """
        Takes a list of strings and returns a numpy array of embeddings.
        The .encode() method automatically batches the inputs for performance.
        """
        print(f"[*] Generating embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        return embeddings