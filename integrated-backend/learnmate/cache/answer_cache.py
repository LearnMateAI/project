"""
A verified semantic cache of accepted chat answers, shared across students.

    lookup(doc, question)    nearest cached questions for this document     (Qdrant ANN)
                               -> cosine >= CACHE_TAU?                        (cheap filter)
                               -> same question, per a duplicate-question     (the verifier)
                                  cross-encoder?
                             => hit: the stored answer, its citations and context
    store(turn)              only answers the judge accepted, in pdf mode

Why this works here in particular: documents are stored once per SHA-256, so every student
who uploads the same lecture notes is talking to the same document id -- and a class
revising for the same exam asks the same questions in different words. On a 3B model on a
laptop CPU a turn is 30-60 seconds; a hit is one embedding, one ANN query and one
cross-encoder pass.

Why the verifier: an embedding threshold alone cannot be set anywhere useful. Paraphrases
of one question spread down to ~0.8 cosine, while "advantages of X" and "disadvantages of
X" sit above 0.95. Any threshold either misses paraphrases or serves wrong answers. The
cross-encoder reads both questions together and is trained on exactly that distinction;
the threshold only has to shortlist. (The same shortlist-then-verify split as retrieval
and reranking, and the idea behind "verified" semantic caches in the literature.)

What is keyed, and why each part is there:

    doc_id / doc_sha     answers are about one document's content
    index_version        a re-ingested document may chunk differently; old answers cite
                         pages of the old chunking -- they stop matching
    model_key            generator identity + CACHE_PROMPT_VERSION: a different model or
                         prompt would not have written this answer
    embedding_model      vectors from two embedding models are not comparable

No user or session id is ever written to an entry. What is cached is an answer about a
document, not a record of who asked; a unit test holds that line.
"""

import hashlib
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .. import config
from ..llm import equivalence
from ..storage import cache_events

logger = logging.getLogger("learnmate.cache")

_POINT_NAMESPACE = uuid.UUID("3c1f2a6e-9b0d-4e57-8a41-5d6c7e8f9a0b")
PAYLOAD_SCHEMA = 1

# Payload fields an entry may carry. The privacy test asserts nothing else is written.
PAYLOAD_FIELDS = frozenset({
    "schema", "doc_id", "doc_sha", "index_version", "model_key", "embedding_model",
    "query_text", "query_norm", "answer", "citations", "contexts", "judge_score",
    "top_score", "created_at", "expires_at", "hit_count", "last_hit_at",
})

_TRAILING = re.compile(r"[\s?.!]+$")
_SPACES = re.compile(r"\s+")


def normalize_query(text: str) -> str:
    """Case, whitespace and trailing punctuation folded: the exact-repeat key."""
    return _TRAILING.sub("", _SPACES.sub(" ", (text or "").strip().lower()))


def model_key(model_id: Optional[str] = None) -> str:
    """Which generator and prompt wrote an answer -- the part of the key a config change moves."""
    if model_id:
        identity = f"registry:{model_id}"
    else:
        identity = f"{config.GENERATOR_BACKEND}:{Path(config.GENERATOR_MODEL).name}"
    raw = f"{identity}|prompt:{config.CACHE_PROMPT_VERSION}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def decide(similarities: Sequence[float], verifier_scores: Optional[Sequence[Optional[float]]],
           tau: float, verifier_threshold: float, use_verifier: bool
           ) -> Tuple[bool, Optional[int], str]:
    """
    The hit rule, as a pure function of the scores. `similarities` are best first.

    Returns (hit, index of the winning candidate, outcome). A verifier that could not run
    (`verifier_scores is None`) is a miss, never a pass: unverifiable is not verified.
    """
    if not similarities:
        return False, None, "miss_empty"
    eligible = [i for i, sim in enumerate(similarities) if sim >= tau]
    if not eligible:
        return False, None, "miss_tau"
    if not use_verifier:
        return True, eligible[0], "hit"
    if verifier_scores is None:
        return False, None, "miss_verifier_unavailable"
    for i in eligible:
        score = verifier_scores[i]
        if score is not None and score >= verifier_threshold:
            return True, i, "hit"
    return False, None, "miss_verifier"


def should_store(state: Dict) -> Tuple[bool, str]:
    """
    Is this finished turn fit to be served to somebody else? (store it, reason)

    Only a judged pdf-mode answer that passed. A general-mode answer came from the
    model's own knowledge and was never checked (JUDGE_GATE_MODES skips it); an unjudged
    one (evaluate=False) was never checked at all. A follow-up whose question the rewrite
    changed leans on a conversation the next student has not had.
    """
    cache = state.get("cache") or {}
    if cache.get("hit"):
        return False, "skip:hit"
    if state.get("mode") != "pdf" or not state.get("contexts"):
        return False, "skip:general"
    verdict = state.get("verdict") or {}
    if not verdict or verdict.get("gated") or verdict.get("cached"):
        return False, "skip:unjudged"
    score = verdict.get("score")
    if not isinstance(score, (int, float)) or score < config.CACHE_MIN_SCORE:
        return False, "skip:low_score"
    if not state.get("passed"):
        return False, "skip:rejected"
    if not (state.get("reply") or "").strip():
        return False, "skip:empty"
    if (not config.CACHE_STORE_FOLLOWUPS
            and normalize_query(state.get("standalone_query") or state.get("query", ""))
            != normalize_query(state.get("query", ""))):
        return False, "skip:followup"
    return True, "stored"


@dataclass
class LookupResult:
    hit: bool
    outcome: str
    similarity: Optional[float] = None
    verifier: Optional[float] = None
    entry_id: Optional[str] = None
    payload: Dict = field(default_factory=dict)
    n_candidates: int = 0
    latency_ms: int = 0

    def summary(self) -> Dict:
        """What the turn records about the lookup -- no answer text, no other question."""
        age = None
        if self.hit and self.payload.get("created_at"):
            age = int(time.time() - float(self.payload["created_at"]))
        return {"hit": self.hit, "reason": self.outcome,
                "similarity": None if self.similarity is None else round(self.similarity, 4),
                "verifier": None if self.verifier is None else round(self.verifier, 4),
                "source_age_s": age, "entry_id": self.entry_id if self.hit else None,
                "lookup_ms": self.latency_ms}


class AnswerCache:
    """The cache collection in Qdrant, and the rules around it."""

    def __init__(self, collection_name: str = None, url: str = None, embeddings=None):
        self.collection_name = collection_name or config.CACHE_COLLECTION
        self.url = url or config.QDRANT_URL
        self._embeddings = embeddings
        self._client = None
        self._ready = False
        self._lock = threading.Lock()

    # --- plumbing -----------------------------------------------------------------------

    @property
    def embeddings(self):
        if self._embeddings is None:
            from ..llm.embeddings import get_embeddings

            self._embeddings = get_embeddings()
        return self._embeddings

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url, api_key=config.QDRANT_API_KEY or None,
                                        timeout=config.QDRANT_TIMEOUT)
        return self._client

    def ensure_collection(self) -> None:
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            from qdrant_client import models

            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.embeddings.dimension, distance=models.Distance.COSINE))
                # doc_id is the tenant: every lookup filters on it.
                self.client.create_payload_index(
                    self.collection_name, "doc_id",
                    field_schema=models.KeywordIndexParams(
                        type=models.KeywordIndexType.KEYWORD, is_tenant=True))
                for name in ("model_key", "embedding_model", "index_version"):
                    self.client.create_payload_index(
                        self.collection_name, name,
                        field_schema=models.PayloadSchemaType.KEYWORD)
                self.client.create_payload_index(
                    self.collection_name, "expires_at",
                    field_schema=models.PayloadSchemaType.FLOAT)
            self._ready = True

    @staticmethod
    def _doc_info(doc_id) -> Optional[Dict]:
        """sha256 and an index version for the document, or None if it is not Ready."""
        from ..storage import pdf_store

        document = pdf_store.get_document(doc_id)
        if not document or not document.get("ingested_at"):
            return None
        ingested = document["ingested_at"]
        return {"doc_sha": document.get("sha256", ""),
                "index_version": ingested.isoformat() if hasattr(ingested, "isoformat")
                else str(ingested)}

    def _filter(self, doc_id: str, info: Dict, key: str):
        from qdrant_client import models

        return models.Filter(must=[
            models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)),
            models.FieldCondition(key="model_key", match=models.MatchValue(value=key)),
            models.FieldCondition(key="embedding_model",
                                  match=models.MatchValue(value=config.EMBEDDING_MODEL)),
            models.FieldCondition(key="index_version",
                                  match=models.MatchValue(value=info["index_version"])),
            models.FieldCondition(key="expires_at", range=models.Range(gt=time.time())),
        ])

    # --- the two operations -------------------------------------------------------------

    def lookup(self, doc_id, question: str, query_vector: Optional[List[float]] = None,
               model_id: Optional[str] = None, tau: Optional[float] = None,
               use_verifier: Optional[bool] = None, log: bool = True) -> LookupResult:
        started = time.perf_counter()
        tau = config.CACHE_TAU if tau is None else tau
        use_verifier = config.CACHE_VERIFIER_ENABLED if use_verifier is None else use_verifier
        doc_key = str(doc_id)

        info = self._doc_info(doc_id)
        if info is None:
            return self._finish(LookupResult(False, "miss_no_document"), started, doc_id, log)

        self.ensure_collection()
        vector = query_vector or self.embeddings.embed_query(question)
        response = self.client.query_points(
            collection_name=self.collection_name, query=vector,
            query_filter=self._filter(doc_key, info, model_key(model_id)),
            limit=max(1, config.CACHE_CANDIDATES), with_payload=True)
        points = list(response.points)
        sims = [float(point.score) for point in points]

        verifier_scores: Optional[List[Optional[float]]] = [None] * len(points)
        if use_verifier and any(sim >= tau for sim in sims):
            norm = normalize_query(question)
            eligible = [i for i, sim in enumerate(sims) if sim >= tau]
            # An exact repeat needs no model to tell it is the same question.
            pending = [i for i in eligible
                       if (points[i].payload or {}).get("query_norm") != norm]
            for i in eligible:
                if i not in pending:
                    verifier_scores[i] = 1.0
            if pending:
                scored = equivalence.score_pairs(
                    [(question, (points[i].payload or {}).get("query_text", ""))
                     for i in pending])
                if scored is None:
                    verifier_scores = None
                else:
                    for i, score in zip(pending, scored):
                        verifier_scores[i] = score

        hit, index, outcome = decide(sims, verifier_scores, tau,
                                     config.CACHE_VERIFIER_THRESHOLD, use_verifier)
        best = index if index is not None else (0 if points else None)
        result = LookupResult(
            hit=hit, outcome=outcome,
            similarity=sims[best] if best is not None else None,
            verifier=(verifier_scores[best] if verifier_scores and best is not None
                      else None),
            entry_id=str(points[best].id) if best is not None else None,
            payload=dict(points[index].payload or {}) if hit else {},
            n_candidates=len(points))
        if hit:
            self._record_hit(result.entry_id, points[index].payload or {})
        return self._finish(result, started, doc_id, log)

    def _finish(self, result: LookupResult, started: float, doc_id, log: bool) -> LookupResult:
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        if log:
            cache_events.log_event("lookup", result.outcome, doc_id=doc_id,
                                   sim=result.similarity, verifier=result.verifier,
                                   latency_ms=result.latency_ms, entry_id=result.entry_id,
                                   n_candidates=result.n_candidates)
        return result

    def _payload(self, doc_id, info: Dict, question: str, answer: str,
                 contexts: Sequence, scores: Sequence[float], judge_score,
                 top_score, model_id: Optional[str]) -> Dict:
        now = time.time()
        citations, stored_contexts = [], []
        for i, doc in enumerate(contexts):
            meta = getattr(doc, "metadata", None) or {}
            chunk_index = meta.get("chunk_index")
            citations.append({"page": meta.get("page_number"),
                              "paragraph": chunk_index + 1
                              if isinstance(chunk_index, int) else None})
            stored_contexts.append({
                "page_number": meta.get("page_number"), "chunk_index": chunk_index,
                "text": getattr(doc, "page_content", ""),
                "score": float(scores[i]) if i < len(scores) else None})
        return {
            "schema": PAYLOAD_SCHEMA,
            "doc_id": str(doc_id),
            "doc_sha": info["doc_sha"],
            "index_version": info["index_version"],
            "model_key": model_key(model_id),
            "embedding_model": config.EMBEDDING_MODEL,
            "query_text": question,
            "query_norm": normalize_query(question),
            "answer": answer,
            "citations": citations,
            "contexts": stored_contexts,
            "judge_score": judge_score,
            "top_score": None if top_score is None else float(top_score),
            "created_at": now,
            "expires_at": now + config.CACHE_TTL_S,
            "hit_count": 0,
            "last_hit_at": None,
        }

    def store(self, doc_id, question: str, answer: str, contexts: Sequence,
              scores: Sequence[float] = (), judge_score=None, top_score=None,
              model_id: Optional[str] = None,
              query_vector: Optional[List[float]] = None) -> Optional[str]:
        """Write one entry. Re-asking an identical question refreshes it in place."""
        from qdrant_client import models

        info = self._doc_info(doc_id)
        if info is None:
            return None
        self.ensure_collection()
        payload = self._payload(doc_id, info, question, answer, contexts, scores,
                                judge_score, top_score, model_id)
        entry_id = str(uuid.uuid5(_POINT_NAMESPACE, "|".join(
            (str(doc_id), payload["model_key"], info["index_version"],
             payload["query_norm"]))))
        vector = query_vector or self.embeddings.embed_query(question)
        self.client.upsert(self.collection_name, points=[
            models.PointStruct(id=entry_id, vector=vector, payload=payload)], wait=True)
        cache_events.log_event("store", "stored", doc_id=doc_id, entry_id=entry_id)
        return entry_id

    def _record_hit(self, entry_id: str, payload: Dict) -> None:
        """Bump the hit counter. Best effort: the event log is the source of truth."""
        try:
            self.client.set_payload(
                self.collection_name,
                payload={"hit_count": int(payload.get("hit_count") or 0) + 1,
                         "last_hit_at": time.time()},
                points=[entry_id])
        except Exception:
            pass

    # --- keeping it honest ----------------------------------------------------------------

    def _delete(self, conditions, reason: str, doc_id=None) -> None:
        from qdrant_client import models

        try:
            if not self.client.collection_exists(self.collection_name):
                return
            self.client.delete(self.collection_name,
                               points_selector=models.FilterSelector(
                                   filter=models.Filter(**conditions)), wait=True)
            cache_events.log_event("invalidate", reason, doc_id=doc_id)
        except Exception as exc:
            logger.warning("Answer cache %s failed: %s", reason, exc)

    def invalidate(self, doc_id, reason: str = "reingest") -> None:
        """Forget every answer about one document -- re-ingested, or deleted."""
        from qdrant_client import models

        self._delete({"must": [models.FieldCondition(
            key="doc_id", match=models.MatchValue(value=str(doc_id)))]}, reason, doc_id)

    def purge_expired(self) -> None:
        from qdrant_client import models

        self._delete({"must": [models.FieldCondition(
            key="expires_at", range=models.Range(lte=time.time()))]}, "expired")

    def purge_embedding_mismatch(self) -> None:
        from qdrant_client import models

        self._delete({"must_not": [models.FieldCondition(
            key="embedding_model", match=models.MatchValue(value=config.EMBEDDING_MODEL))]},
            "embedding_model")


_CACHE: Optional[AnswerCache] = None


def get_answer_cache() -> AnswerCache:
    global _CACHE
    if _CACHE is None:
        _CACHE = AnswerCache()
    return _CACHE


def invalidate_document(doc_id, reason: str) -> None:
    """For ingestion and deletion: drop a document's answers, quietly, if a cache exists."""
    if config.VECTOR_BACKEND != "qdrant":
        return
    try:
        get_answer_cache().invalidate(doc_id, reason)
    except Exception as exc:
        logger.warning("Could not invalidate cached answers for %s: %s", doc_id, exc)
