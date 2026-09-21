"""
Question equivalence: do two questions ask for the same answer?

The semantic answer cache (learnmate/cache) finds candidates by embedding similarity, and
embedding similarity is exactly the wrong tool for the last step. "What are the advantages
of a sole proprietorship?" and "...disadvantages..." sit at cosine ~0.95 under MiniLM --
they share every content word but one -- and serving one's answer to the other is worse
than serving nothing.

A cross-encoder trained on duplicate-question pairs (Quora Question Pairs) reads the two
questions together, attention running across both, and is trained on precisely that
distinction. It is the same arrangement as retrieval: the bi-encoder shortlists, the
cross-encoder decides. Same loading pattern as rerank.py, and for the same reasons.
"""

import threading
from typing import List, Optional, Sequence, Tuple

from .. import config
from .rerank import _sigmoid

_CACHE = {}
_LOAD_LOCK = threading.Lock()
# HF fast tokenizers are not safe to share between threads mid-call ("Already borrowed"),
# and a worker pool can run several lookups at once.
_PREDICT_LOCK = threading.Lock()
_UNAVAILABLE = set()


def _load(model_name: str):
    if model_name in _UNAVAILABLE:
        return None
    if model_name in _CACHE:
        return _CACHE[model_name]
    with _LOAD_LOCK:
        if model_name in _UNAVAILABLE:
            return None
        if model_name not in _CACHE:
            try:
                import torch
                from sentence_transformers import CrossEncoder

                print(f"[*] Loading question verifier: {model_name} (first load only)...")
                # Identity activation, sigmoid applied below: the model's config does not
                # say which activation it was trained with, and the library's default for
                # single-label models has changed between releases. Doing it explicitly
                # keeps the threshold's meaning fixed.
                _CACHE[model_name] = CrossEncoder(model_name,
                                                  activation_fn=torch.nn.Identity())
            except Exception as exc:
                print(f"[!] Question verifier {model_name!r} unavailable "
                      f"({type(exc).__name__}: {exc}); cache lookups will miss.")
                _UNAVAILABLE.add(model_name)
                return None
    return _CACHE[model_name]


def available(model_name: str = None) -> bool:
    return _load(model_name or config.CACHE_VERIFIER_MODEL) is not None


def score_pairs(pairs: Sequence[Tuple[str, str]], model_name: str = None
                ) -> Optional[List[float]]:
    """
    Probability that each pair asks the same thing, in [0, 1].

    None -- not an empty list -- when the verifier could not run, so the cache can treat
    "unverifiable" as a miss rather than as a pass.
    """
    if not pairs:
        return []
    model = _load(model_name or config.CACHE_VERIFIER_MODEL)
    if model is None:
        return None
    try:
        with _PREDICT_LOCK:
            logits = model.predict(list(pairs), show_progress_bar=False)
    except Exception as exc:
        print(f"[!] Question verification failed ({type(exc).__name__}: {exc}).")
        return None
    return [_sigmoid(float(logit)) for logit in logits]
