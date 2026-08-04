"""
A LangChain VectorStore backed by a Qdrant **server**.

Server mode, never embedded. `QdrantClient(path=...)` runs Qdrant inside this process
against a local directory and takes an exclusive file lock on it, which means exactly one
process can hold the corpus and nothing else on the network can read it. That is the mode
the previous implementation used and the reason a second script could not run while the
chat agent was open. This module only ever constructs the client with a URL, and refuses
a `path` setting outright rather than silently falling back to it.

Qdrant is a purpose-built vector database, so unlike the MongoDB fallback the similarity
search is a real HNSW index on the server side: filtering by document and scoring happen
where the vectors live, and neither the vectors nor the payloads are pulled across the
wire to be scored here.

Scores are raw cosine similarity in [-1, 1], the same scale MongoVectorStore returns, so
RELEVANCE_THRESHOLD means one thing regardless of which backend is configured.
"""

import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from .. import config
from ..llm.embeddings import get_embeddings

# Deterministic point ids. Qdrant accepts only uint64 or UUID ids, so the natural key
# (doc_id, page_number, chunk_index) is hashed into a UUID5. Re-ingesting a document
# therefore overwrites its points in place instead of appending a second copy of them.
_POINT_NAMESPACE = uuid.UUID("6f8a1d3e-2b41-4c9a-9d2f-7e5b0c1a4d88")


class QdrantUnavailable(RuntimeError):
    """Raised when the Qdrant server cannot be reached, with the URL that was tried."""


def _point_id(doc_id, page_number, chunk_index) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{doc_id}:{page_number}:{chunk_index}"))


class QdrantVectorStore(VectorStore):
    """Chunk vectors in a Qdrant server, filtered by document."""

    def __init__(self, embedding: Embeddings = None, url: str = None,
                 api_key: str = None, collection_name: str = None):
        self._embedding = embedding or get_embeddings()
        self.url = url or config.QDRANT_URL
        self.api_key = api_key or config.QDRANT_API_KEY or None
        self.collection_name = collection_name or config.QDRANT_COLLECTION
        self._client = None
        self._collection_ready = False

    # --- Connection ------------------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            try:
                # url= only. Passing path= here would silently start an embedded instance
                # and take a directory lock, which is the mode this project moved off.
                client = QdrantClient(url=self.url, api_key=self.api_key,
                                      timeout=config.QDRANT_TIMEOUT)
                client.get_collections()  # the client is lazy; force a real round trip
            except Exception as exc:
                raise QdrantUnavailable(
                    f"Cannot reach the Qdrant server at {self.url}. Start one with "
                    f"`docker compose up -d qdrant` (see docker-compose.yml), or set "
                    f"LEARNMATE_QDRANT_URL. Original error: {type(exc).__name__}: {exc}"
                ) from exc
            self._client = client
        return self._client

    def ensure_collection(self) -> None:
        """Create the collection and its payload index if they do not exist yet."""
        if self._collection_ready:
            return

        from qdrant_client import models

        if not self.client.collection_exists(self.collection_name):
            size = self._embedding.dimension
            print(f"[*] Creating Qdrant collection {self.collection_name!r} "
                  f"({size}-d, cosine)...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=size, distance=models.Distance.COSINE),
            )

        # Every query filters on doc_id. Without a payload index Qdrant falls back to a
        # full scan for the filter, which defeats the point of using a vector database.
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="doc_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            # Already present; Qdrant has no create-if-missing for payload indexes.
            pass

        self._collection_ready = True

    def _doc_filter(self, doc_id=None, pages: Optional[List[int]] = None):
        """Build a Qdrant filter, or None when nothing is being narrowed."""
        from qdrant_client import models

        conditions = []
        if doc_id is not None:
            conditions.append(models.FieldCondition(
                key="doc_id", match=models.MatchValue(value=str(doc_id))))
        if pages:
            conditions.append(models.FieldCondition(
                key="page_number", match=models.MatchAny(any=list(pages))))
        return models.Filter(must=conditions) if conditions else None

    # --- LangChain plumbing ----------------------------------------------------------

    @property
    def embeddings(self) -> Embeddings:
        return self._embedding

    @classmethod
    def from_texts(cls, texts: List[str], embedding: Embeddings,
                   metadatas: Optional[List[dict]] = None, **kwargs: Any
                   ) -> "QdrantVectorStore":
        store = cls(embedding=embedding, **kwargs)
        store.add_texts(texts, metadatas)
        return store

    # --- Writing ---------------------------------------------------------------------

    def add_texts(self, texts: Iterable[str], metadatas: Optional[List[dict]] = None,
                  **kwargs: Any) -> List[str]:
        """Embed and upsert chunks, in batches so a large document is not one huge request."""
        from qdrant_client import models

        texts = list(texts)
        if not texts:
            return []

        self.ensure_collection()
        metadatas = metadatas or [{} for _ in texts]
        vectors = self._embedding.embed_documents(texts)

        points, ids = [], []
        for text, metadata, vector in zip(texts, metadatas, vectors):
            doc_id = str(metadata.get("doc_id", ""))
            page_number = metadata.get("page_number", 0)
            chunk_index = metadata.get("chunk_index", 0)
            identifier = _point_id(doc_id, page_number, chunk_index)

            points.append(models.PointStruct(
                id=identifier,
                vector=vector,
                payload={
                    "doc_id": doc_id,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "text": text,
                    "filename": metadata.get("filename"),
                    "source": metadata.get("source"),
                },
            ))
            ids.append(identifier)

        for start in range(0, len(points), config.QDRANT_BATCH_SIZE):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[start:start + config.QDRANT_BATCH_SIZE],
                wait=True,
            )
        return ids

    def delete(self, ids: Optional[List[str]] = None, doc_id=None, **kwargs: Any) -> bool:
        """Delete by point id, or every point belonging to one document."""
        from qdrant_client import models

        self.ensure_collection()
        if doc_id is not None:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=self._doc_filter(doc_id)),
                wait=True,
            )
            return True
        if ids:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=list(ids)),
                wait=True,
            )
            return True
        return False

    # --- Reading ---------------------------------------------------------------------

    def similarity_search(self, query: str, k: int = None, doc_id=None,
                          **kwargs: Any) -> List[Document]:
        return [doc for doc, _ in
                self.similarity_search_with_score(query, k=k, doc_id=doc_id, **kwargs)]

    def similarity_search_with_score(self, query: str, k: int = None, doc_id=None,
                                     **kwargs: Any) -> List[Tuple[Document, float]]:
        """Top-k chunks with cosine similarity, optionally restricted to one document."""
        k = k or config.TOP_K
        self.ensure_collection()

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=self._embedding.embed_query(query),
            query_filter=self._doc_filter(doc_id),
            limit=k,
            with_payload=True,
        )
        return [(self._to_document(point.payload, point.id), float(point.score))
                for point in response.points]

    @staticmethod
    def _to_document(payload: Dict[str, Any], point_id=None) -> Document:
        payload = payload or {}
        return Document(
            page_content=payload.get("text", ""),
            metadata={
                "chunk_id": str(point_id or ""),
                "doc_id": payload.get("doc_id", ""),
                "page_number": payload.get("page_number"),
                "chunk_index": payload.get("chunk_index"),
                "filename": payload.get("filename"),
            },
        )

    # --- Convenience -----------------------------------------------------------------

    def count(self, doc_id=None) -> int:
        self.ensure_collection()
        return self.client.count(
            collection_name=self.collection_name,
            count_filter=self._doc_filter(doc_id),
            exact=True,
        ).count

    def chunks_for(self, doc_id, limit: int = None, pages: Optional[List[int]] = None
                   ) -> List[Document]:
        """
        Every chunk of one document in reading order.

        Scrolled in pages rather than fetched in one call: a 300-page PDF is a few
        thousand points and Qdrant caps a single scroll response. Ordering is applied
        here because scroll returns points in id order, and the ids are content hashes.
        """
        self.ensure_collection()
        query_filter = self._doc_filter(doc_id, pages)

        documents, offset = [], None
        while True:
            batch, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=config.QDRANT_BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            documents.extend(self._to_document(p.payload, p.id) for p in batch)
            if offset is None or (limit and len(documents) >= limit):
                break

        documents.sort(key=lambda d: (d.metadata.get("page_number") or 0,
                                      d.metadata.get("chunk_index") or 0))
        return documents[:limit] if limit else documents

    def describe_backend(self) -> str:
        return f"Qdrant server at {self.url} (collection {self.collection_name!r})"
