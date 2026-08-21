"""
Generating study material, and reading it back.

One entry point, `generate`, dispatching over two axes:

                  scope="passage"                 scope="document"
    mcq           generate_resource               generate_document_items
    practice_qsn  generate_resource               generate_document_items
    keypoints     generate_resource               generate_document_items
    summary       generate_resource               summarize_document

The distinction is not a performance knob. A passage is one continuous extract that fits
the context window -- optionally the pages most relevant to a topic -- and answers "five
questions about directors' duties". A document run splits the whole PDF into groups, asks
each for its share and pools the results, which is the only way to get forty questions
that are actually about the book rather than about its opening pages. Summaries fold
instead of pooling, because a summary is one artefact, so they have their own function.

This module never decides *when* to run: it is called from the job worker, and every call
here can take minutes.
"""

from typing import Dict, List, Optional

from learnmate import config as engine_config
from learnmate.ingestion import build_source_text
from learnmate.resource_agent import (
    generate_document_items,
    generate_resource,
    summarize_document,
)
from learnmate.resource_agent.tasks import TASK_NAMES
from learnmate.storage import content_store

from .. import config
from . import ownership as access

# What the frontend already sends, mapped to what the engine calls them. Accepted so the
# existing React code keeps working while it is migrated to the engine's names.
_ALIASES = {
    "key_points": "keypoints",
    "keypoint": "keypoints",
    "explanation_summary": "summary",
    "practice_questions": "practice_qsn",
    "practise_qsn": "practice_qsn",
    "short_qsn": "practice_qsn",
    "mcqs": "mcq",
}

# Pooling across a document only works for list-shaped resources; a summary is one piece
# of prose and folds instead. See document_summary.py.
POOLED_TASKS = ("mcq", "practice_qsn", "keypoints")


def resolve_task(resource_type: str) -> str:
    """Turn what a client asked for into an engine task name."""
    name = (resource_type or "").strip().lower()
    name = _ALIASES.get(name, name)
    if name not in TASK_NAMES:
        raise ValueError(
            f"Unsupported resource type {resource_type!r}; expected one of "
            f"{', '.join(TASK_NAMES)}."
        )
    return name


def serialize(resource: Dict) -> Dict:
    """
    One resource, in the shape the frontend reads.

    `verification_status` is gone, replaced by what the evaluator actually decided.
    A hardcoded "Unverified" was a placeholder for exactly this: `accepted` says whether
    it cleared the judge, `score` and `threshold` say by how much, and `n_attempts` says
    whether it needed a retry to get there.
    """
    created_at = resource.get("created_at")
    verdict = resource.get("verdict") or {}

    return {
        "id": str(resource["_id"]),
        "document_id": str(resource.get("doc_id")) if resource.get("doc_id") else None,
        "resource_type": resource.get("task"),
        "content": resource.get("content"),
        "accepted": bool(resource.get("accepted")),
        "score": resource.get("score"),
        "threshold": resource.get("threshold", engine_config.EVALUATOR_THRESHOLD),
        "n_attempts": resource.get("n_attempts", len(resource.get("attempts") or [])),
        "reasoning": verdict.get("reasoning"),
        "params": resource.get("params", {}),
        "created_at": created_at.isoformat() if created_at else None,
    }


def serialize_detail(resource: Dict) -> Dict:
    """
    One resource with its whole attempt trail.

    The trail is what makes a disappointing result answerable rather than mysterious:
    which gate rejected the first attempt, what it objected to, and what changed.
    """
    detail = serialize(resource)
    detail["verdict"] = resource.get("verdict")
    detail["attempts"] = resource.get("attempts", [])
    detail["source_preview"] = resource.get("source_preview", "")
    return detail


def generate(user_id: str, doc_id: str, resource_type: str, scope: str = "passage",
             topic: str = None, pages: Optional[List[int]] = None, count: int = None,
             per_page: int = None, evaluate: bool = True, threshold: int = None,
             on_progress=None, summary_style: str = None, difficulty: str = None,
             model_id: str = None) -> Dict:
    """
    Generate one resource, start to finish. Slow: seconds to minutes.

    Returns the stored resource, serialized. Raises ValueError when the request cannot
    be satisfied -- an unknown type, a document that never finished processing, a
    document with no text to work from.
    """
    task = resolve_task(resource_type)
    document = access.require_ready_document(user_id, doc_id)
    document_id = document["_id"]

    common = {
        "doc_id": document_id,
        "user_id": user_id,
        "threshold": threshold,
        "evaluate": evaluate,
        "persist": True,
        # Nobody is watching stdout on the worker; progress goes to the job record.
        "verbose": False,
        "on_progress": on_progress,
        "summary_style": summary_style,
        "difficulty": difficulty,
        "model_id": model_id,
        "topic": topic,
    }

    if scope == "document":
        if task == "summary":
            # count is sentences here, and None lets it size itself to the document.
            result = summarize_document(count=count, **common)
        else:
            if per_page is not None and count is not None:
                raise ValueError(
                    "Pass either count (a total across the document) or per_page (a rate "
                    "per page), not both."
                )
            if per_page is None and count is None:
                # A total is the question people actually ask; the rate is opt-in.
                count = 20
            result = generate_document_items(task, count=count, per_page=per_page,
                                             **common)
    else:
        # --- passage scope ---
        # build_source_text turns a topic into the whole pages that best match it, or
        # takes the pages it was given, or falls back to the opening of the document.
        source = build_source_text(document_id, topic=topic, pages=pages)
        if not source.strip():
            raise ValueError(
                f"No usable text found in {document.get('filename', 'this document')}"
                + (f" for {topic!r}." if topic else ".")
            )
        result = generate_resource(task, source, count=count or 5, **common)

    resource_id = result.get("resource_id")
    if not resource_id:
        # persist=True, so this only happens if the store call failed; returning the
        # in-memory result would hand back something no listing will ever show again.
        raise RuntimeError("The resource was generated but could not be stored.")

    stored = content_store.get_resource(resource_id)
    detail = serialize_detail(stored)
    # Reported by the whole-document paths: how many were asked for versus produced,
    # which is the difference between "the document is short" and "something went wrong".
    for key in ("requested", "generated", "groups", "per_page", "timings"):
        if key in result:
            detail[key] = result[key]
    return detail


def list_resources(user_id: str, doc_id: str = None, resource_type: str = None
                   ) -> List[Dict]:
    """The user's resources, newest first, optionally for one document or type."""
    if doc_id is not None:
        # Checked so a listing cannot be used to probe which document ids exist.
        access.require_document(user_id, doc_id)

    task = resolve_task(resource_type) if resource_type else None

    return [serialize(resource) for resource in content_store.list_resources(
        doc_id=doc_id, task=task, user_id=user_id, limit=config.MAX_RESOURCES)]


def get_resource(user_id: str, resource_id: str) -> Dict:
    """One resource, with its attempt trail."""
    return serialize_detail(access.require_resource(user_id, resource_id))


def delete_resource(user_id: str, resource_id: str) -> Dict:
    """Delete one of the user's resources."""
    access.require_resource(user_id, resource_id)
    content_store.delete_resource(resource_id, user_id=user_id)
    return {"removed": True}
