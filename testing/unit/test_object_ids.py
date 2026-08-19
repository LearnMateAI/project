"""U-04 — Mongo id coercion (`learnmate/storage/ids.py`)."""

from bson import ObjectId

from learnmate.storage.ids import as_object_id, coerce_id


def test_coerce_hex_and_objectid():
    oid = ObjectId()
    assert coerce_id(oid) == oid
    assert coerce_id(str(oid)) == oid


def test_coerce_junk_is_none():
    assert coerce_id("not-an-id") is None
    assert coerce_id("") is None


def test_as_object_id_passes_junk_through():
    assert as_object_id("not-an-id") == "not-an-id"
    assert as_object_id(None) is None
    oid = ObjectId()
    assert as_object_id(str(oid)) == oid
