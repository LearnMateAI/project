"""
The cleaned text of every page, kept whole.

Stored separately from the chunks because the two answer different questions. Chunks are
sized and overlapped for *retrieval*, so reassembling a page from them repeats ~150
characters at every boundary and starts mid-sentence. Resource generation wants the page
as it reads, and a page is also the natural unit for `--pages 12-18`.

This is what makes a resource-generation session possible: without it, `build_source_text`
would have nothing but chunks to work from.
"""

from typing import Dict, List, Optional, Union

from bson import ObjectId
from pymongo import UpdateOne

from .. import config
from .ids import coerce_id
from .mongo import get_db


def _collection():
    return get_db()[config.COLL_PAGES]


def store_pages(doc_id: Union[str, ObjectId], pages: List[Dict]) -> int:
    """
    Store the cleaned text of every page. Returns how many were written.

    Upserted on (doc_id, page_number), so re-ingesting a document refreshes its pages
    rather than piling up a second copy beside them.
    """
    oid = coerce_id(doc_id)
    operations = [
        UpdateOne(
            {"doc_id": oid, "page_number": page["page_number"]},
            {"$set": {"doc_id": oid,
                      "page_number": page["page_number"],
                      "page_index": page["page_index"],
                      "text": page["page_content"]}},
            upsert=True,
        )
        for page in pages
    ]
    if not operations:
        return 0
    _collection().bulk_write(operations, ordered=False)
    return len(operations)


def get_pages(doc_id: Union[str, ObjectId], page_numbers: Optional[List[int]] = None
              ) -> List[Dict]:
    """Cleaned page text in reading order, optionally only the pages named."""
    query: Dict = {"doc_id": coerce_id(doc_id)}
    if page_numbers:
        query["page_number"] = {"$in": list(page_numbers)}
    return list(_collection()
                .find(query, {"page_number": 1, "text": 1})
                .sort("page_number", 1))


def count_pages(doc_id: Union[str, ObjectId]) -> int:
    """
    How many pages of text are stored for a document.

    Cheaper than get_pages when the question is only "was this ingested" -- which is what
    the API asks before letting a generation run start.
    """
    return _collection().count_documents({"doc_id": coerce_id(doc_id)})


def delete_pages(doc_id: Union[str, ObjectId]) -> int:
    """Drop a document's stored page text. Returns how many pages were removed."""
    return _collection().delete_many({"doc_id": coerce_id(doc_id)}).deleted_count
