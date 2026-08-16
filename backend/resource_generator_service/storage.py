from datetime import datetime, timezone


def store_generated_resource(resources_collection, document_id: str, resource_type: str, content) -> dict:
    """
    Persists one generated resource (SRS §3.10 Generated Resource entity).
    `content` is a string for summaries, a list of strings for key points.
    """
    resource = {
        "document_id": document_id,
        "resource_type": resource_type,
        "content": content,
        # Simplified version of FR-14 (Content Verification): a full
        # implementation runs a second LLM call (Evaluator Agent) to grade
        # output quality and trigger regeneration if it fails a threshold
        # (Dinura's components-Dinura/learnmate/evaluator/ does this
        # properly — not yet integrated into this shared backend).
        "verification_status": "Unverified",
        "created_at": datetime.now(timezone.utc),
    }
    result = resources_collection.insert_one(resource)
    return {
        "id": str(result.inserted_id),
        "document_id": document_id,
        "resource_type": resource_type,
        "content": content,
        "verification_status": resource["verification_status"],
        "created_at": resource["created_at"].isoformat(),
    }