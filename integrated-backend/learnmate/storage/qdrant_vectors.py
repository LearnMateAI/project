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

Two collection layouts are understood, and detected rather than assumed:

    legacy   one unnamed dense vector, plus a hashed word-count vector named "sparse" on
             collections created after the first hybrid attempt. What this project has
             always created, and still creates by default.
    v2       named vectors: "dense" (cosine) and "bm25" (sparse, Modifier.IDF), with
             doc_id indexed as the tenant key. Built by scripts/reindex_qdrant.py. This is
             what `query()` fuses over -- see learnmate/retrieval/retriever.py.
"""

import re
import threading
import uuid
import hashlib
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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


class UnsupportedStrategy(ValueError):
    """The collection's layout cannot serve the retrieval strategy that was asked for."""


# Strategies `query()` understands, and which named sparse vector each one reads.
_SPARSE_FOR = {"bm25": "bm25", "rrf": "bm25", "dbsf": "bm25",
               "splade": "splade", "rrf_splade": "splade"}
QUERY_STRATEGIES = ("dense",) + tuple(_SPARSE_FOR)


def _point_id(doc_id, page_number, chunk_index) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{doc_id}:{page_number}:{chunk_index}"))

def _to_sparse(text: str) -> dict:
    """Basic term-frequency sparse vector for hybrid search."""
    words = re.findall(r'\w+', text.lower())
    counts = Counter(words)
    indices = []
    values = []
    for w, c in counts.items():
        idx = int(hashlib.md5(w.encode()).hexdigest(), 16) % 1000000
        if idx not in indices:
            indices.append(idx)
            values.append(float(c))
    return {"indices": indices, "values": values}


class QdrantVectorStore(VectorStore):
    """Chunk vectors in a Qdrant server, filtered by document."""

    def __init__(self, embedding: Embeddings = None, url: str = None,
                 api_key: str = None, collection_name: str = None, schema: str = None,
                 splade: Optional[bool] = None):
        self._embedding = embedding or get_embeddings()
        self.url = url or config.QDRANT_URL
        self.api_key = api_key or config.QDRANT_API_KEY or None
        self.collection_name = collection_name or config.QDRANT_COLLECTION
        # Only consulted when this process has to *create* the collection.
        self._create_schema = (schema or config.QDRANT_SCHEMA).lower()
        self._create_splade = config.SPLADE_ENABLED if splade is None else splade
        self._client = None
        self._collection_ready = False
        self._ready_lock = threading.Lock()
        # Settled by ensure_collection: True only when the collection actually has a sparse
        # vector to write to and query. Never assumed -- see the note there.
        self._hybrid = False
        # "legacy" or "v2", and for v2 the names of its sparse vectors. Also settled by
        # ensure_collection, from what the server says the collection holds.
        self.schema = "legacy"
        self._sparse_names: frozenset = frozenset()

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
        """
        Create the collection and its payload index if they do not exist yet, and work out
        whether hybrid search is available on it.

        A collection made before hybrid retrieval existed has no sparse vector configured,
        and Qdrant cannot add one afterwards -- `update_collection(sparse_vectors_config=)`
        answers "Not existing vector name error: sparse". Recreating it is the only route,
        and that is destructive, so it is the operator's call and not something this does
        on their behalf while they are looking the other way.

        Until they make it, `_hybrid` stays False and both writing and searching run
        dense-only, exactly as they did before. That keeps an existing corpus working
        rather than failing every upsert and every query with a 400.
        """
        if self._collection_ready:
            return

        # The worker and the warm-up thread can both arrive here on a fresh install, and
        # two concurrent create_collection calls end with the second one raising.
        with self._ready_lock:
            if self._collection_ready:
                return
            self._prepare_collection()
            self._collection_ready = True

    def _prepare_collection(self) -> None:
        from qdrant_client import models

        if not self.client.collection_exists(self.collection_name):
            if self._create_schema == "v2":
                self.create_v2_collection(splade=self._create_splade)
            else:
                size = self._embedding.dimension
                print(f"[*] Creating Qdrant collection {self.collection_name!r} "
                      f"({size}-d, cosine + sparse)...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=size, distance=models.Distance.COSINE),
                    sparse_vectors_config={"sparse": models.SparseVectorParams()},
                )

        params = self.client.get_collection(self.collection_name).config.params
        self._detect_schema(params)

        if self.schema == "legacy" and not self._hybrid:
            print(f"[!] Collection {self.collection_name!r} predates hybrid search and has "
                  f"no sparse vector; running dense-only. To enable it, delete the "
                  f"collection and re-ingest (the PDFs and page text are in MongoDB, so "
                  f"nothing is lost but the embedding time).")

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

    def _detect_schema(self, params) -> None:
        """Read the layout off the collection's own config: named dense vector => v2."""
        vectors = params.vectors
        sparse = params.sparse_vectors or {}
        if isinstance(vectors, dict) and config.QDRANT_DENSE_NAME in vectors:
            self.schema = "v2"
            self._sparse_names = frozenset(sparse)
            self._hybrid = False
        else:
            self.schema = "legacy"
            self._sparse_names = frozenset()
            self._hybrid = bool(sparse)

    def create_v2_collection(self, splade: bool = False) -> None:
        """
        Create this collection in the v2 layout.

        `Modifier.IDF` is what makes the sparse vector BM25 rather than word counting: the
        server keeps document frequencies per term and multiplies them into the query's
        weights at search time, so no process has to hold corpus statistics. doc_id is the
        tenant key -- every query filters on it -- and page_number is indexed for the
        page-restricted scrolls resource generation does.
        """
        from qdrant_client import models

        size = self._embedding.dimension
        sparse = {config.QDRANT_SPARSE_NAME:
                  models.SparseVectorParams(modifier=models.Modifier.IDF)}
        if splade:
            sparse[config.QDRANT_SPLADE_NAME] = models.SparseVectorParams()
        print(f"[*] Creating Qdrant collection {self.collection_name!r} (v2: "
              f"{size}-d dense + {', '.join(sparse)})...")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={config.QDRANT_DENSE_NAME: models.VectorParams(
                size=size, distance=models.Distance.COSINE)},
            sparse_vectors_config=sparse,
        )
        doc_index = (models.KeywordIndexParams(
            type=models.KeywordIndexType.KEYWORD, is_tenant=True)
                     if config.QDRANT_TENANT_INDEX else models.PayloadSchemaType.KEYWORD)
        self.client.create_payload_index(self.collection_name, "doc_id",
                                         field_schema=doc_index)
        self.client.create_payload_index(self.collection_name, "page_number",
                                         field_schema=models.PayloadSchemaType.INTEGER)

    def supports(self, strategy: str) -> bool:
        """Can this collection serve `strategy` through query()?"""
        self.ensure_collection()
        if strategy == "dense":
            return True
        sparse = _SPARSE_FOR.get(strategy)
        if sparse is None or self.schema != "v2":
            return False
        name = config.QDRANT_SPARSE_NAME if sparse == "bm25" else config.QDRANT_SPLADE_NAME
        return name in self._sparse_names

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
        return self.upsert_chunks(texts, metadatas, vectors)

    def _v2_vectors(self, texts: Sequence[str], dense: Sequence[List[float]]
                    ) -> List[Dict[str, Any]]:
        """Named vectors for a v2 point: dense, BM25 and -- if the collection has it -- SPLADE."""
        from qdrant_client import models

        from ..retrieval.sparse import bm25_doc_vector, get_splade
        from .retrieval_meta import resolve_avgdl

        avgdl = resolve_avgdl(texts)
        splade = None
        if config.QDRANT_SPLADE_NAME in self._sparse_names:
            splade = get_splade(config.SPLADE_MODEL).encode_documents(list(texts))

        named = []
        for i, (text, vector) in enumerate(zip(texts, dense)):
            indices, values = bm25_doc_vector(text, config.BM25_K1, config.BM25_B, avgdl)
            point = {config.QDRANT_DENSE_NAME: vector,
                     config.QDRANT_SPARSE_NAME: models.SparseVector(
                         indices=indices, values=values)}
            if splade is not None:
                s_idx, s_val = splade[i]
                point[config.QDRANT_SPLADE_NAME] = models.SparseVector(
                    indices=s_idx, values=s_val)
            named.append(point)
        return named

    def upsert_chunks(self, texts: Sequence[str], metadatas: Sequence[dict],
                      dense: Sequence[List[float]]) -> List[str]:
        """
        Write chunks whose dense vectors are already computed.

        Split out of add_texts so scripts/reindex_qdrant.py can move a corpus into a v2
        collection by copying its existing embeddings instead of re-embedding every chunk.
        """
        from qdrant_client import models

        self.ensure_collection()
        texts = list(texts)
        if self.schema == "v2":
            from ..retrieval.sparse import ANALYZER_VERSION

            point_vectors = self._v2_vectors(texts, dense)
        else:
            # A bare list addresses the unnamed dense vector; the dict form addresses it
            # as "" alongside the named sparse one. Only the second is legal on a
            # collection that has a sparse vector configured, and only the first on one
            # that does not.
            point_vectors = [
                {"": vector, "sparse": models.SparseVector(**_to_sparse(text))}
                if self._hybrid else vector
                for text, vector in zip(texts, dense)
            ]

        points, ids = [], []
        for text, metadata, point_vector in zip(texts, metadatas, point_vectors):
            doc_id = str(metadata.get("doc_id", ""))
            page_number = metadata.get("page_number", 0)
            chunk_index = metadata.get("chunk_index", 0)
            identifier = _point_id(doc_id, page_number, chunk_index)
            payload = {
                "doc_id": doc_id,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "text": text,
                "filename": metadata.get("filename"),
                "source": metadata.get("source"),
            }
            if self.schema == "v2":
                # Which analyzer built the bm25 vector: a query analysed differently
                # would silently miss, so the index records what it was built with.
                payload["analyzer"] = ANALYZER_VERSION
            points.append(models.PointStruct(id=identifier, vector=point_vector,
                                             payload=payload))
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
        """
        Top-k chunks, optionally restricted to one document.

        **The score means different things in the two modes**, and callers that threshold
        it need to know which they are in:

            dense-only   raw cosine similarity in [-1, 1], which is what
                         RELEVANCE_THRESHOLD is calibrated against
            hybrid       a reciprocal-rank-fusion score, which measures *rank* and not
                         similarity -- the top hit scores high by construction however
                         poor the match. Measured over 40 documents: 0.64, 0.50, 0.40,
                         0.38, 0.34, against a RELEVANCE_THRESHOLD of 0.25.

        In practice chat_agent/retrieve.py reranks and decides the mode on the
        cross-encoder's score, so it is insulated from this. Its fallback path -- reranker
        disabled or failing to load -- is not, and would read almost everything as
        relevant. That is a live problem to settle before hybrid is turned on for real.
        """
        # This file imports `models` per method rather than at module scope, so a method
        # that uses it needs its own import; without this the whole read path raised
        # NameError.
        from qdrant_client import models

        k = k or config.TOP_K
        self.ensure_collection()

        if self.schema == "v2":
            # Plain cosine on the named dense vector. Fusion on a v2 collection is asked
            # for explicitly, through query(), by a caller that knows its score is a rank.
            return [(doc, score) for doc, score, _ in self.query(
                "dense", query, self._embedding.embed_query(query), k, doc_id=doc_id)]

        if not self._hybrid:
            # Dense-only, and identical to the pre-hybrid behaviour: one vector, cosine
            # scores, nothing fused.
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=self._embedding.embed_query(query),
                query_filter=self._doc_filter(doc_id),
                limit=k,
                with_payload=True,
            )
            return [(self._to_document(point.payload, point.id), float(point.score))
                    for point in response.points]

        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=self._embedding.embed_query(query),
                    limit=k,
                ),
                models.Prefetch(
                    query=models.SparseVector(**_to_sparse(query)),
                    using="sparse",
                    limit=k,
                )
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=self._doc_filter(doc_id),
            limit=k,
            with_payload=True,
        )
        return [(self._to_document(point.payload, point.id), float(point.score))
                for point in response.points]

    def _sparse_query(self, strategy: str, text: str):
        """The query-side sparse vector for `strategy`, or None when it has no terms."""
        from qdrant_client import models

        from ..retrieval.sparse import bm25_query_vector, get_splade

        if _SPARSE_FOR[strategy] == "splade":
            indices, values = get_splade(config.SPLADE_MODEL).encode_query(text)
            name = config.QDRANT_SPLADE_NAME
        else:
            indices, values = bm25_query_vector(text)
            name = config.QDRANT_SPARSE_NAME
        if not indices:
            # All stopwords ("what is it?"). An empty sparse query matches nothing, and a
            # fused one would then be the dense branch alone -- which is what the caller
            # gets, explicitly, rather than a request Qdrant may reject.
            return None, name
        return models.SparseVector(indices=indices, values=values), name

    def query(self, strategy: str, text: str, query_vector: List[float], k: int,
              doc_id=None, prefetch_k: Optional[int] = None, want_dense: bool = True
              ) -> List[Tuple[Document, float, Optional[float]]]:
        """
        One retrieval strategy, executed inside Qdrant.

        Returns (document, score, dense_cos) best first. `score` is whatever the strategy
        ranks by -- cosine, BM25, or a fused rank score -- and is only comparable within
        one call. `dense_cos` is the cosine between the query and the chunk's own dense
        vector, fetched alongside, so a caller can apply RELEVANCE_THRESHOLD whatever the
        ranking was. It is None only when `want_dense` is off.

        The document filter is set on every prefetch as well as on the fused query. The
        outer filter alone would let each branch spend its candidate budget on *other*
        documents' chunks before fusion discarded them.
        """
        from qdrant_client import models

        self.ensure_collection()
        if not self.supports(strategy):
            raise UnsupportedStrategy(
                f"Collection {self.collection_name!r} ({self.schema}) cannot serve the "
                f"{strategy!r} strategy. Build a v2 collection with "
                f"scripts/reindex_qdrant.py.")

        doc_filter = self._doc_filter(doc_id)
        dense_name = config.QDRANT_DENSE_NAME if self.schema == "v2" else None
        # The unnamed legacy vector cannot be asked for by name; it only ever serves
        # "dense", where the score already is the cosine.
        fetch_dense = want_dense and strategy != "dense" and dense_name is not None
        with_vectors = [dense_name] if fetch_dense else False

        if strategy == "dense":
            response = self.client.query_points(
                collection_name=self.collection_name, query=query_vector,
                using=dense_name, query_filter=doc_filter, limit=k, with_payload=True)
        else:
            sparse, sparse_name = self._sparse_query(strategy, text)
            if strategy in ("bm25", "splade"):
                if sparse is None:
                    return []
                response = self.client.query_points(
                    collection_name=self.collection_name, query=sparse, using=sparse_name,
                    query_filter=doc_filter, limit=k, with_payload=True,
                    with_vectors=with_vectors)
            else:
                prefetch_k = max(prefetch_k or config.HYBRID_PREFETCH, k)
                prefetch = [models.Prefetch(query=query_vector, using=dense_name,
                                            filter=doc_filter, limit=prefetch_k)]
                if sparse is not None:
                    prefetch.append(models.Prefetch(query=sparse, using=sparse_name,
                                                    filter=doc_filter, limit=prefetch_k))
                if strategy == "dbsf":
                    fusion = models.FusionQuery(fusion=models.Fusion.DBSF)
                elif config.RRF_K > 0:
                    fusion = models.RrfQuery(rrf=models.Rrf(k=config.RRF_K))
                else:
                    fusion = models.FusionQuery(fusion=models.Fusion.RRF)
                response = self.client.query_points(
                    collection_name=self.collection_name, prefetch=prefetch, query=fusion,
                    query_filter=doc_filter, limit=k, with_payload=True,
                    with_vectors=with_vectors)

        results = []
        for point in response.points:
            dense_cos = float(point.score) if strategy == "dense" else None
            if fetch_dense:
                vector = point.vector.get(dense_name) if isinstance(point.vector, dict) \
                    else point.vector
                if vector:
                    # Qdrant stores cosine vectors normalised and the query embedding is
                    # normalised too, so the dot product is the cosine.
                    dense_cos = float(sum(a * b for a, b in zip(vector, query_vector)))
            results.append((self._to_document(point.payload, point.id), float(point.score),
                            dense_cos))
        return results

    def scroll_points(self, doc_id=None, with_vectors: bool = True):
        """
        Every point of one document (or the collection), payload and dense vector.

        For scripts/reindex_qdrant.py, which copies embeddings between collections.
        Yields (payload, dense_vector or None).
        """
        self.ensure_collection()
        dense_name = config.QDRANT_DENSE_NAME if self.schema == "v2" else ""
        offset = None
        while True:
            batch, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=self._doc_filter(doc_id),
                limit=config.QDRANT_BATCH_SIZE, offset=offset,
                with_payload=True, with_vectors=with_vectors)
            for point in batch:
                vector = point.vector
                if isinstance(vector, dict):
                    vector = vector.get(dense_name)
                yield point.payload or {}, vector
            if offset is None:
                break

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

    def ping(self) -> Dict[str, Any]:
        """
        Is the server reachable, and does the collection exist yet?

        Deliberately does not call ensure_collection: creating a collection needs the
        embedding model's dimension, which means loading the embedding model. A health
        check that pulls 90 MB of weights into memory on a fresh install is not a health
        check. A missing collection is normal before the first ingest.
        """
        exists = self.client.collection_exists(self.collection_name)
        return {
            "backend": "qdrant",
            "detail": self.describe_backend(),
            "collection_exists": exists,
            "chunks": self.count() if exists else 0,
        }
