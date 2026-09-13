"""
The PDF bytes themselves, in GridFS.

An uploaded PDF is kept whole, in the database, alongside the chunks derived from it, so a
document can be re-read, re-chunked or handed back to a user without depending on the
uploader's filesystem. GridFS rather than a plain field because a document can exceed
MongoDB's 16 MB per-document limit.

This module owns bytes in and bytes out. The record describing them lives in
documents.py, and the two are written together by `documents.store_pdf`.
"""

from pathlib import Path
from typing import Optional, Tuple, Union

import gridfs
from bson import ObjectId

from .. import config
from .mongo import get_db


def bucket() -> gridfs.GridFSBucket:
    """The GridFS bucket PDFs are stored in."""
    return gridfs.GridFSBucket(get_db(), bucket_name=config.GRIDFS_BUCKET)


def read_source(source: Union[str, Path, bytes], filename: str = None) -> Tuple[bytes, str]:
    """
    Read an upload into bytes and check it is one this system will accept.

    Split out from storing so a caller can validate an upload -- and learn its size and
    name -- before anything is written. The ingestion pipeline needs that to refuse a
    second PDF for a session without first storing the file it is about to reject.

    Every upload path goes through here, so the size limit holds for a CLI path argument
    and an HTTP upload alike; a limit enforced at one of the callers is a limit the other
    caller does not have.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"No such file: {path}")
        data = path.read_bytes()
        filename = filename or path.name
    else:
        data = bytes(source)
        filename = filename or "upload.pdf"

    if not data:
        raise ValueError("Refusing to store an empty file.")

    if len(data) > config.MAX_PDF_BYTES:
        raise ValueError(
            f"{filename} is {len(data) / 1_048_576:.1f} MB, over the "
            f"{config.MAX_PDF_MB:g} MB upload limit."
        )

    return data, filename


def put(filename: str, data: bytes, digest: str, content_type: str = None) -> ObjectId:
    """Write bytes into GridFS and return the id to store on the document record."""
    return bucket().upload_from_stream(
        filename, data,
        metadata={
            "sha256": digest,
            "content_type": content_type or "application/pdf",
        })


def get(gridfs_id) -> Optional[bytes]:
    """Read a stored PDF back out. Returns None when the id is missing."""
    if not gridfs_id:
        return None
    stream = bucket().open_download_stream(gridfs_id)
    try:
        return stream.read()
    finally:
        stream.close()


def drop(gridfs_id) -> None:
    """Delete stored bytes, tolerating a record whose bytes are already gone."""
    if not gridfs_id:
        return
    try:
        bucket().delete(gridfs_id)
    except gridfs.NoFile:
        pass
