"""
Sentence-Transformers embeddings behind LangChain's Embeddings interface.

Implemented directly rather than via langchain-huggingface so the project keeps a single
transformers/torch pin: that package tracks its own compatible range and pulling it in
would force a downgrade of the versions already installed here.

The model loads once per process and is shared, which matters because both ingestion and
every retrieval call ask for it.
"""

from typing import List

from langchain_core.embeddings import Embeddings

from .. import config

_MODEL_CACHE = {}


def _load(model_name: str):
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        print(f"[*] Loading embedding model: {model_name} (first load only)...")
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


class LearnMateEmbeddings(Embeddings):
    """all-MiniLM-L6-v2 by default: 384 dimensions, fast enough to embed a book on CPU."""

    def __init__(self, model_name: str = None, normalize: bool = True):
        self.model_name = model_name or config.EMBEDDING_MODEL
        # Normalised vectors make cosine similarity a plain dot product, which is what the
        # NumPy fallback in MongoVectorStore relies on to stay fast.
        self.normalize = normalize
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = _load(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Vector width, needed when declaring the Atlas vector index."""
        model = self.model
        # sentence-transformers renamed this getter in v5 and the old name now warns, so
        # the current name is tried first. Falls back to embedding a token and measuring
        # the result if neither exists.
        for attr in ("get_embedding_dimension", "get_sentence_embedding_dimension"):
            getter = getattr(model, attr, None)
            if callable(getter):
                size = getter()
                if size:
                    return int(size)
        return len(self.embed_query("dimension probe"))

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            normalize_embeddings=self.normalize,
            show_progress_bar=len(texts) > 64,
            batch_size=32,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> List[float]:
        vector = self.model.encode([text], normalize_embeddings=self.normalize)[0]
        return vector.tolist()


_EMBEDDINGS = None


def get_embeddings() -> LearnMateEmbeddings:
    """Process-wide embeddings instance."""
    global _EMBEDDINGS
    if _EMBEDDINGS is None:
        _EMBEDDINGS = LearnMateEmbeddings()
    return _EMBEDDINGS
