from resource_generator_service.explanation_summary import generate_summary
from resource_generator_service.key_points import generate_key_points
from resource_generator_service.storage import store_generated_resource

MAX_CONTEXT_CHARS = 15000  # keeps the prompt a reasonable size and cost


def build_document_text(chunks_collection, document_id: str) -> str:
    """
    Reassembles a document's stored chunks (Day 7) back into one text block,
    in original order, capped to a reasonable length for the prompt.
    """
    chunks = list(
        chunks_collection.find({"document_id": document_id}).sort("chunk_index", 1)
    )
    full_text = "\n\n".join(c["text"] for c in chunks)
    return full_text[:MAX_CONTEXT_CHARS]


def generate_resource(chunks_collection, resources_collection, document_id: str, resource_type: str) -> dict:
    """
    Orchestrates one resource-generation request: build context from stored
    chunks, call the appropriate generator, do a basic verification check,
    and store the result. Raises ValueError on any failure (caught in
    api/resources.py).
    """
    document_text = build_document_text(chunks_collection, document_id)
    if not document_text.strip():
        raise ValueError("This document has no processed content yet. Please wait for processing to finish.")

    if resource_type == "summary":
        content = generate_summary(document_text)
    elif resource_type == "key_points":
        content = generate_key_points(document_text)
    else:
        raise ValueError(f"Unsupported resource type: {resource_type}")

    if not content or (isinstance(content, list) and len(content) == 0):
        raise ValueError("Generation produced an empty result. Please try again.")

    return store_generated_resource(resources_collection, document_id, resource_type, content)