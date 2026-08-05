"""
A LangChain VectorStore backed by a MongoDB collection.

The alternative to the Qdrant backend, selected with LEARNMATE_VECTOR_BACKEND=mongodb.
It exists so the system can run without a second service: vectors go in the same external
database that already holds the PDFs, page text and generated content. Qdrant is the
better choice when it is available -- it has a real HNSW index and does its filtering
server-side -- but one fewer moving part is sometimes worth more than that.

Vectors live in `chunks.embedding`, beside the documents they came from. There is no
embedded database and no local cache directory, so every process reads one shared corpus.

Similarity is computed one of two ways, chosen by what the server can actually do:

    $vectorSearch   Atlas only, an approximate-nearest-neighbour index, scales to millions
    NumPy           everything else, an exact scan of the candidate chunks

The fallback is not a degraded mode for a study corpus. A few thousand 384-dimension
vectors score in a couple of milliseconds and the result is exact rather than approximate;
Atlas only starts to win once the corpus outgrows memory. The capability is probed once
and cached, so pointing LEARNMATE_MONGODB_URI at Atlas switches path with no code change.

Both paths return the same thing: raw cosine similarity in [-1, 1]. Atlas reports cosine
remapped to [0, 1], so it is converted back here -- otherwise RELEVANCE_THRESHOLD would
silently mean two different things on the two backends.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import numpy as np
from bson import ObjectId
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from pymongo import UpdateOne
from pymongo.errors import PyMongoError

from .. import config
from ..llm.embeddings import get_embeddings
from .mongo import get_db, supports_vector_search


def _as_object_id(value) -> Union[ObjectId, Any]:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return value


class MongoVectorStore(VectorStore):
    """Chunk vectors in MongoDB, with Atlas $vectorSearch when the server offers it."""

    def __init__(self, embedding: Embeddings = None, collection_name: str = None,
                 index_name: str = None):
        self._embedding = embedding or get_embeddings()
        self.collection_name = collection_name or config.COLL_CHUNKS
        self.index_name = index_name or config.VECTOR_INDEX_NAME
        self._vector_search_supported: Optional[bool] = None

    # --- LangChain plumbing ----------------------------------------------------------

    @property
    def embeddings(self) -> Embeddings:
        return self._embedding

    @property
    def collection(self):
        return get_db()[self.collection_name]

    @classmethod
    def from_texts(cls, texts: List[str], embedding: Embeddings,
                   metadatas: Optional[List[dict]] = None, **kwargs: Any) -> "MongoVectorStore":
        store = cls(embedding=embedding, **kwargs)
        store.add_texts(texts, metadatas)
        return store

    # --- Writing ---------------------------------------------------------------------

    def add_texts(self, texts: Iterable[str], metadatas: Optional[List[dict]] = None,
                  **kwargs: Any) -> List[str]:
        """
        Embed and upsert chunks.

        Keyed on (doc_id, page_number, chunk_index), so re-ingesting a document replaces
        its chunks instead of piling up a second copy beside them.
        """
        texts = list(texts)
        if not texts:
            return []

        metadatas = metadatas or [{} for _ in texts]
        vectors = self._embedding.embed_documents(texts)
        now = datetime.now(timezone.utc)

        operations, keys = [], []
        for text, metadata, vector in zip(texts, metadatas, vectors):
            doc_id = _as_object_id(metadata.get("doc_id"))
            key = {
                "doc_id": doc_id,
                "page_number": metadata.get("page_number", 0),
                "chunk_index": metadata.get("chunk_index", 0),
            }
            payload = {
                **key,
                "text": text,
                "embedding": vector,
                "filename": metadata.get("filename"),
                "source": metadata.get("source"),
                "updated_at": now,
            }
            operations.append(UpdateOne(key, {"$set": payload}, upsert=True))
            keys.append(f"{doc_id}:{key['page_number']}:{key['chunk_index']}")

        self.collection.bulk_write(operations, ordered=False)
        return keys

    def delete(self, ids: Optional[List[str]] = None, doc_id=None, **kwargs: Any) -> bool:
        """Delete by chunk id, or every chunk of one document."""
        if doc_id is not None:
            self.collection.delete_many({"doc_id": _as_object_id(doc_id)})
            return True
        if ids:
            self.collection.delete_many({"_id": {"$in": [_as_object_id(i) for i in ids]}})
            return True
        return False

    # --- Reading ---------------------------------------------------------------------

    def _can_vector_search(self) -> bool:
        if self._vector_search_supported is None:
            self._vector_search_supported = supports_vector_search(get_db())
        return self._vector_search_supported

    def similarity_search(self, query: str, k: int = None, doc_id=None,
                          **kwargs: Any) -> List[Document]:
        return [doc for doc, _ in
                self.similarity_search_with_score(query, k=k, doc_id=doc_id, **kwargs)]

    def similarity_search_with_score(self, query: str, k: int = None, doc_id=None,
                                     **kwargs: Any) -> List[Tuple[Document, float]]:
        """Top-k chunks with raw cosine similarity, optionally restricted to one document."""
        k = k or config.TOP_K
        vector = self._embedding.embed_query(query)

        query_filter: Dict[str, Any] = {}
        if doc_id is not None:
            query_filter["doc_id"] = _as_object_id(doc_id)

        if self._can_vector_search():
            try:
                return self._atlas_search(vector, k, query_filter)
            except PyMongoError:
                # An Atlas cluster without the index built yet reaches here. Score exactly
                # instead of returning nothing, and stop probing.
                self._vector_search_supported = False

        return self._numpy_search(vector, k, query_filter)

    def _atlas_search(self, vector: List[float], k: int,
                      query_filter: Dict[str, Any]) -> List[Tuple[Document, float]]:
        stage: Dict[str, Any] = {
            "index": self.index_name,
            "path": "embedding",
            "queryVector": vector,
            # Oversampling the ANN candidate pool is the standard accuracy/latency trade;
            # 10x is Atlas's own recommendation for small k.
            "numCandidates": max(k * 10, 100),
            "limit": k,
        }
        if query_filter:
            stage["filter"] = query_filter

        pipeline = [
            {"$vectorSearch": stage},
            {"$project": {"text": 1, "page_number": 1, "doc_id": 1, "chunk_index": 1,
                          "filename": 1, "score": {"$meta": "vectorSearchScore"}}},
        ]

        results = []
        for row in self.collection.aggregate(pipeline):
            # Atlas reports cosine as (1 + cos) / 2; undo it so both paths agree.
            cosine = 2.0 * float(row.get("score", 0.0)) - 1.0
            results.append((self._to_document(row), cosine))
        return results

    def _numpy_search(self, vector: List[float], k: int,
                      query_filter: Dict[str, Any]) -> List[Tuple[Document, float]]:
        """
        Exact cosine similarity over the candidate chunks.

        Both stored and query vectors are L2-normalised by LearnMateEmbeddings, so cosine
        similarity is a plain dot product and the whole scan is one matrix multiply.
        """
        projection = {"text": 1, "page_number": 1, "doc_id": 1, "chunk_index": 1,
                      "filename": 1, "embedding": 1}
        rows = list(self.collection.find(query_filter, projection))
        if not rows:
            return []

        matrix = np.asarray([row["embedding"] for row in rows], dtype=np.float32)
        query_vector = np.asarray(vector, dtype=np.float32)

        # Guard against vectors stored unnormalised (e.g. written by an older ingest).
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0] = 1.0
        query_norm = np.linalg.norm(query_vector) or 1.0

        scores = (matrix @ query_vector) / (norms * query_norm)

        top = np.argsort(-scores)[:k]
        return [(self._to_document(rows[i]), float(scores[i])) for i in top]

    @staticmethod
    def _to_document(row: Dict[str, Any]) -> Document:
        return Document(
            page_content=row.get("text", ""),
            metadata={
                "chunk_id": str(row.get("_id", "")),
                "doc_id": str(row.get("doc_id", "")),
                "page_number": row.get("page_number"),
                "chunk_index": row.get("chunk_index"),
                "filename": row.get("filename"),
            },
        )

    # --- Convenience -----------------------------------------------------------------

    def count(self, doc_id=None) -> int:
        query_filter = {"doc_id": _as_object_id(doc_id)} if doc_id is not None else {}
        return self.collection.count_documents(query_filter)

    def chunks_for(self, doc_id, limit: int = None, pages: Optional[List[int]] = None
                   ) -> List[Document]:
        """Chunks of one document in reading order, optionally limited to some pages."""
        query_filter: Dict[str, Any] = {"doc_id": _as_object_id(doc_id)}
        if pages:
            query_filter["page_number"] = {"$in": list(pages)}

        cursor = (self.collection
                  .find(query_filter, {"text": 1, "page_number": 1, "doc_id": 1,
                                       "chunk_index": 1, "filename": 1})
                  .sort([("page_number", 1), ("chunk_index", 1)]))
        if limit:
            cursor = cursor.limit(limit)
        return [self._to_document(row) for row in cursor]

    def describe_backend(self) -> str:
        """Which similarity path is in use, for the CLI to report."""
        return ("Atlas $vectorSearch" if self._can_vector_search()
                else "exact NumPy cosine (no Atlas vector index on this server)")


