"""
What each kind of job actually does.

Three kinds, each a thin wrapper over a service call plus a progress callback:

    ingest    extract, clean, chunk and embed one uploaded PDF
    resource  generate one piece of study material
    chat      answer one message

Thin on purpose. Everything here is also reachable synchronously, and the only difference
between the two is that a job passes `on_progress` and stores the return value on a record
instead of in a response. Putting real logic in this file would make the queue a second
implementation of the API.

`run` returns whatever should land in the job's `result` field, and raises on failure --
the worker records both.
"""

import logging
import re
import time
from typing import Dict

from learnmate.ingestion import ingest_pdf
from learnmate.storage import jobs as job_store
from learnmate.storage import pdf_store

from ..services import chat as chat_service
from ..services import resources as resource_service

logger = logging.getLogger("learnmate.api.jobs")

# The engine's nodes log for a terminal: "[*] Generating mcq (attempt 1/2)...",
# "[!] Structural check FAILED: ...". Those markers mean nothing in a UI, and they do not
# always lead the string -- whole_document prefixes "Group 2/5: " onto a nested message --
# so they are removed wherever they appear rather than stripped from the front.
_MARKER = re.compile(r"\[[*!+=]\]\s*")


def _reporter(job_id: str):
    """
    A progress callback that writes onto the job record.

    The only formatting done here is dropping those markers: the messages themselves were
    already written to be read.
    """
    def report(message: str) -> None:
        job_store.set_progress(job_id, _MARKER.sub("", str(message)).strip())

    return report


# How often the streamed reply is flushed to the job record. A 3B model emits several
# tokens a second and the client polls every 300-1500ms, so writing on every token would
# be a Mongo round trip per token to deliver text nobody reads until the next poll. A
# fifth of a second is below what reads as lag and roughly an order of magnitude fewer
# writes.
_STREAM_FLUSH_S = 0.2


def _token_reporter(job_id: str):
    """
    A callback that streams the reply onto the job record as it is written.

    Throttled, and safe to throttle: the chat agent sends the accumulated text rather than
    each new token (see chat_agent/helpers._emit_token), so a skipped call loses nothing --
    the next one carries everything it would have said.

    The final flush is what makes the throttle correct rather than merely cheap. Without
    it the last fragment before the generation ends could be dropped, and the client would
    sit on a visibly truncated answer for the second or two until the result lands.
    """
    state = {"last_flush": 0.0, "pending": None}

    def report(text: str) -> None:
        state["pending"] = text
        now = time.monotonic()
        if now - state["last_flush"] < _STREAM_FLUSH_S:
            return
        state["last_flush"] = now
        state["pending"] = None
        job_store.set_partial(job_id, text)

    def flush() -> None:
        if state["pending"] is not None:
            job_store.set_partial(job_id, state["pending"])
            state["pending"] = None

    report.flush = flush
    return report


# --- The three kinds --------------------------------------------------------------------

def _run_ingest(job: Dict) -> Dict:
    """
    Ingest one already-stored PDF.

    The bytes are read back out of GridFS rather than carried through the queue: a job
    record is small and a 10 MB PDF held in memory from upload until a worker picks it up
    is not, and the upload handler has already stored it either way.
    """
    params = job["params"]
    doc_id = params["document_id"]

    data = pdf_store.get_pdf_bytes(doc_id)
    if data is None:
        raise ValueError("The uploaded file could not be read back for processing.")

    report = _reporter(str(job["_id"]))
    report("Reading the document...")

    result = ingest_pdf(
        data,
        filename=params.get("filename"),
        user_id=job["user_id"],
        verbose=False,
        on_progress=report,
    )

    return {
        "document_id": str(result["doc_id"]),
        "pages": result.get("n_pages"),
        "chunks": result.get("n_chunks"),
        # True when the PDF was already indexed -- somebody had uploaded the same bytes
        # before -- so nothing was re-embedded.
        "skipped": result.get("skipped", False),
        "elapsed_s": result.get("elapsed_s"),
    }


def _run_resource(job: Dict) -> Dict:
    """Generate one resource."""
    params = job["params"]
    return resource_service.generate(
        user_id=job["user_id"],
        doc_id=params["document_id"],
        resource_type=params["resource_type"],
        scope=params.get("scope", "passage"),
        topic=params.get("topic"),
        pages=params.get("pages"),
        count=params.get("count"),
        per_page=params.get("per_page"),
        evaluate=params.get("evaluate", True),
        threshold=params.get("threshold"),
        on_progress=_reporter(str(job["_id"])),
    )


def _run_chat(job: Dict) -> Dict:
    """Answer one message, streaming the reply onto the record as it is written."""
    params = job["params"]
    on_token = _token_reporter(str(job["_id"]))
    try:
        return chat_service.send_message(
            user_id=job["user_id"],
            session_id=params["session_id"],
            message=params["message"],
            evaluate=params.get("evaluate", True),
            on_progress=_reporter(str(job["_id"])),
            on_token=on_token,
        )
    finally:
        # In `finally` so a turn that fails mid-generation still leaves the text it did
        # produce on the record, rather than whatever the last throttled write happened
        # to catch.
        on_token.flush()


RUNNERS = {
    "ingest": _run_ingest,
    "resource": _run_resource,
    "chat": _run_chat,
}


def run(job: Dict):
    """Dispatch one job to its runner."""
    runner = RUNNERS.get(job.get("kind"))
    if runner is None:
        raise ValueError(f"Unknown job kind {job.get('kind')!r}.")
    return runner(job)
