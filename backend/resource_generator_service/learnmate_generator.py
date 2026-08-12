"""
resource generation via components-Dinura's local pipeline, replacing the
Gemini-based generator.py for live use (that file stays, unused, for explainability --
same pattern as Day 10's process_document retirement).

The one real behavior change this forces: generation now takes 60-120s of local CPU
inference instead of a few seconds against Gemini's API. A synchronous request-response
doesn't work at that duration (client/proxy timeouts, and it blocks a FastAPI worker for
two minutes). So this is a two-phase flow instead of a single call:

  1. create_pending_resource   -- insert a placeholder immediately, return it (202)
  2. generate_resource_via_learnmate  -- background task, fills the placeholder in

The frontend polls GET /api/resources/{id} until verification_status is no longer
"Generating".
"""

from datetime import datetime, timezone
from bson import ObjectId

from services.learnmate_bridge import run_generate

# Must match learnmate.resource_agent.TASK_NAMES exactly -- hardcoded here rather than
# imported, since this backend's venv deliberately doesn't have learnmate installed
# (see learnmate_bridge.py's docstring for why).
TASK_NAMES = ["mcq", "summary", "keypoints", "practice_qsn"]


def create_pending_resource(resources_collection, document_id: str, resource_type: str) -> dict:
    """Insert a placeholder resource record and return it in the API's existing shape."""
    resource = {
        "document_id": document_id,
        "resource_type": resource_type,
        "content": None,
        "verification_status": "Generating",
        "score": None,
        "threshold": None,
        "reasoning": None,
        "created_at": datetime.now(timezone.utc),
    }
    result = resources_collection.insert_one(resource)
    return {
        "id": str(result.inserted_id),
        "document_id": document_id,
        "resource_type": resource_type,
        "content": None,
        "verification_status": "Generating",
        "score": None,
        "threshold": None,
        "reasoning": None,
        "created_at": resource["created_at"].isoformat(),
    }


def generate_resource_via_learnmate(resources_collection, resource_id: str,
                                     task: str, learnmate_doc_id: str, count: int = 5) -> None:
    """
    Background task: run generation, then fill in the placeholder created above.

    verification_status becomes "Verified" (judge accepted it) or "Unverified" (judge
    rejected it, but content is still stored and shown -- learnmate's own design choice,
    carried through here rather than hidden).
    """
    try:
        result = run_generate(task, learnmate_doc_id, count=count)
        resources_collection.update_one(
            {"_id": ObjectId(resource_id)},
            {"$set": {
                "content": result["content"],
                "verification_status": "Verified" if result["accepted"] else "Unverified",
                "score": result.get("score"),
                "threshold": result.get("threshold"),
                "reasoning": result.get("reasoning"),
            }},
        )
    except Exception as e:
        resources_collection.update_one(
            {"_id": ObjectId(resource_id)},
            {"$set": {"verification_status": "Failed", "reasoning": str(e)}},
        )
