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

# "(attempt 1/2)" is retry bookkeeping. In a terminal it is the useful part of the line --
# it is how you see the judge rejecting things -- but on screen it invites a reader to
# wonder what went wrong with the attempt they never saw, during a wait they can do nothing
# about. Dropped for the UI only; the CLI still prints it, and the real count is recorded on
# the turn either way (chat_agent/persist stores len(attempts)).
_ATTEMPT = re.compile(r"\s*\(attempt \d+\s*/\s*\d+\)")


def _reporter(job_id: str):
    """
    A progress callback that writes onto the job record.

    Formatting is limited to dropping the terminal markers and the attempt counter: the
    messages themselves were already written to be read.
    """
    def report(message: str) -> None:
        text = _MARKER.sub("", str(message))
        text = _ATTEMPT.sub("", text)
        job_store.set_progress(job_id, text.strip())

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
    state = {"last_flush": 0.0, "pending": None, "frozen": False}

    def report(text: str) -> None:
        if state["frozen"]:
            return
        state["pending"] = text
        now = time.monotonic()
        if now - state["last_flush"] < _STREAM_FLUSH_S:
            return
        state["last_flush"] = now
        state["pending"] = None
        job_store.set_partial(job_id, text)

    def flush() -> None:
        if state["frozen"] or state["pending"] is None:
            return
        job_store.set_partial(job_id, state["pending"])
        state["pending"] = None

    def freeze() -> None:
        """
        Stop writing. Called once a complete reply has been published.

        A rejected turn generates a second time, and those tokens would otherwise stream
        over the answer the reader is part-way through -- replacing a finished paragraph
        with a half-written one, which reads as the assistant having second thoughts in
        public. The regeneration still happens; it just happens off-screen, and if it wins
        the finished result swaps the text in once, cleanly.

        The pending write is dropped rather than flushed: it holds an earlier prefix of
        text that has already been superseded by the complete reply.
        """
        state["frozen"] = True
        state["pending"] = None

    report.flush = flush
    report.freeze = freeze
    return report


def _reply_reporter(job_id: str, on_token):
    """
    A callback that publishes the first complete reply, mid-job.

    This is the milestone the chat turn is really built around now. Writing the answer is
    the fast half of a turn; judging it -- and regenerating when the judge says no -- is the
    slow half, and none of it changes the text unless the retry actually scores higher.
    So the answer is handed over as soon as it exists, and the verdict catches up later in
    the finished result.

    Only the *first* one is published, which is what makes the reader's copy stable: see
    freeze() above.
    """
    published = {"done": False}

    def report(text: str, attempt: int) -> None:
        if published["done"]:
            return
        published["done"] = True
        on_token.freeze()
        job_store.set_reply_ready(job_id, text)

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
        summary_style=params.get("summary_style"),
        difficulty=params.get("difficulty"),
        model_id=params.get("model_id"),
        on_progress=_reporter(str(job["_id"])),
    )


def _run_chat(job: Dict) -> Dict:
    """
    Answer one message, streaming the reply onto the record as it is written.

    Two milestones rather than one. The tokens arrive on `progress.partial` as they are
    generated; then `progress.reply_ready` goes up the moment the reply is whole, which is
    long before the job is done -- the judge has not run, and may yet force a regeneration.
    A client can render an answer at that point instead of a cursor, and pick up the score
    when the result lands.
    """
    params = job["params"]
    job_id = str(job["_id"])
    on_token = _token_reporter(job_id)
    try:
        return chat_service.send_message(
            user_id=job["user_id"],
            session_id=params["session_id"],
            message=params["message"],
            evaluate=params.get("evaluate", True),
            model_id=params.get("model_id"),
            on_progress=_reporter(job_id),
            on_token=on_token,
            on_reply=_reply_reporter(job_id, on_token),
        )
    finally:
        # In `finally` so a turn that fails mid-generation still leaves the text it did
        # produce on the record, rather than whatever the last throttled write happened
        # to catch. A no-op once a complete reply has been published.
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
