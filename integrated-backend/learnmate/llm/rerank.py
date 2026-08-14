"""
Cross-encoder reranking: re-scoring retrieved chunks by reading them with the question.

The vector search that produced those chunks never saw the question and the chunk
together. It embedded each independently, months apart in the case of the chunks, and
compared the two points. That is fast enough to search a whole corpus, and it is a
famously blunt instrument at the top of the list: a chunk that shares the question's
vocabulary outranks one that actually answers it.

A cross-encoder reads the pair -- `(question, chunk)` in one forward pass, with attention
running across both -- and emits a single relevance logit. It cannot search anything,
because scoring every chunk in the corpus that way would take minutes. So the two are
used together, which is the standard arrangement:

    vector search   thousands of chunks -> ~20 candidates    (fast, approximate)
    cross-encoder   ~20 candidates      -> the best 3        (slow, accurate)

ms-marco-MiniLM-L-6-v2 is 22M parameters. Twenty pairs is about a tenth of a second on
CPU, against a generation measured in tens of seconds -- so on this system reranking is
effectively free, and it is the cheapest accuracy available anywhere in the pipeline.

    runtime.py     the GGUF weights
    registry.py    the chat-model wrappers
    embeddings.py  the bi-encoder that does the searching
    rerank.py      the cross-encoder that does the ranking   <- this file
"""

import math
from typing import List, Optional, Sequence, Tuple

from .. import config

_RERANKER_CACHE = {}

# Set once the configured model has failed to load, so a missing or broken reranker costs
# one warning rather than one per turn. Retrieval falls back to vector order, which is
# exactly how this system behaved before reranking existed.
_UNAVAILABLE = set()


def _load(model_name: str):
    """Load (or reuse) the cross-encoder. Returns None if it cannot be loaded."""
    if model_name in _UNAVAILABLE:
        return None
    if model_name not in _RERANKER_CACHE:
        try:
            # Imported lazily and from sentence-transformers, which is already a hard
            # dependency for the bi-encoder -- reranking adds no new package, only a
            # ~90 MB download on first use.
            from sentence_transformers import CrossEncoder

            print(f"[*] Loading reranker: {model_name} (first load only)...")
            _RERANKER_CACHE[model_name] = CrossEncoder(model_name)
        except Exception as exc:
            print(f"[!] Reranker {model_name!r} unavailable ({type(exc).__name__}: {exc}); "
                  f"falling back to vector-search order.")
            _UNAVAILABLE.add(model_name)
            return None
    return _RERANKER_CACHE[model_name]


def available() -> bool:
    """Whether reranking is switched on and the model can actually be loaded."""
    if not config.RERANK_ENABLED:
        return False
    return _load(config.RERANK_MODEL) is not None


def _sigmoid(logit: float) -> float:
    """
    Squash a raw cross-encoder logit into [0, 1].

    ms-marco models emit an unbounded logit, roughly -11 to +11, which is awkward to
    threshold against and meaningless to show a user. A sigmoid puts it on the same scale
    as the cosine score it replaces, and maps the model's own decision boundary (logit 0)
    onto a readable 0.5.
    """
    # Guard the exponential: math.exp(800) overflows, and a logit that extreme is a
    # certainty either way.
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-min(logit, 60.0)))
    return math.exp(max(logit, -60.0)) / (1.0 + math.exp(max(logit, -60.0)))


def rerank(query: str, candidates: Sequence, top_k: Optional[int] = None
           ) -> Optional[List[Tuple[object, float]]]:
    """
    Re-score `candidates` against `query`, best first.

    `candidates` are LangChain Documents. Returns `(document, score)` pairs with the score
    in [0, 1], truncated to `top_k`.

    Returns **None** -- not an empty list -- when reranking did not run, so the caller can
    tell "the reranker rejected everything" from "there was no reranker". The first means
    nothing relevant was retrieved; the second means fall back to the vector scores.
    """
    if not config.RERANK_ENABLED or not candidates:
        return None

    model = _load(config.RERANK_MODEL)
    if model is None:
        return None

    top_k = top_k or config.TOP_K
    pairs = [(query, getattr(doc, "page_content", str(doc))) for doc in candidates]

    try:
        logits = model.predict(pairs, show_progress_bar=False)
    except Exception as exc:
        # A pair too long for the model's window, or a torch error mid-batch. Retrieval
        # must not lose a turn over the *optional* half of it.
        print(f"[!] Reranking failed ({type(exc).__name__}: {exc}); "
              f"falling back to vector-search order.")
        return None

    scored = [(doc, _sigmoid(float(logit))) for doc, logit in zip(candidates, logits)]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
