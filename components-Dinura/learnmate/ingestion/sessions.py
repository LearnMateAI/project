"""
What a session is: one PDF, opened for one purpose.

A session records two things at ingest time -- which PDF it is about, and what it is for:

    chat      the PDF will be asked questions about, through the chat agent
    resource  the PDF will have MCQs, summaries and key points generated from it

Both purposes need exactly the same ingestion work (the same chunks, the same vectors,
the same stored page text), so the kind is not an optimisation. It is a statement of
intent, checked when a command runs so that `generate` against a session opened for chat
tells the user plainly rather than quietly doing something they did not set up.

Opening a second session for a PDF that is already ingested costs nothing -- the chunks
exist, so `ingest_pdf` takes its "already ingested" path and only writes the new binding.
That is why refusing a mismatch here is cheap advice rather than an obstacle.

Two rules live in this file:

    check_free()   one PDF per session -- a different PDF into a used session is refused
    require_kind() a session opened for one purpose is not silently used for the other
"""

from typing import Iterable, Optional, Sequence, Tuple, Union

from .. import config
from ..storage import content_store

# The purposes a session can be opened for.
SESSION_KINDS: Tuple[str, ...] = ("chat", "resource")

# What a user may type. "both" is there for one PDF that serves the whole workflow --
# the plural and verb forms because "resources" and "generate" are what people reach for.
_ALIASES = {
    "chat": ("chat",),
    "resource": ("resource",),
    "resources": ("resource",),
    "resource_gen": ("resource",),
    "generate": ("resource",),
    "both": SESSION_KINDS,
    "all": SESSION_KINDS,
}

# How each kind reads in a sentence, for error messages.
_LABELS = {"chat": "chat", "resource": "resource generation"}


def normalise_kinds(value: Union[str, Iterable[str], None]) -> Tuple[str, ...]:
    """
    Turn what a caller passed into a tuple of valid kinds.

    Accepts a single name, one of the aliases above, or an iterable of names, so an HTTP
    handler passing `["chat", "resource"]` and a CLI passing `"both"` both work.
    """
    if value is None:
        return ("chat",)

    names: Sequence[str] = [value] if isinstance(value, str) else list(value)

    kinds = []
    for name in names:
        resolved = _ALIASES.get(str(name).strip().lower())
        if resolved is None:
            raise ValueError(
                f"Unknown session kind {name!r}; expected one of "
                f"{', '.join(sorted(_ALIASES))}."
            )
        for kind in resolved:
            if kind not in kinds:
                kinds.append(kind)

    # Ordered by SESSION_KINDS rather than by what the user typed, so the stored value is
    # the same however it was requested and two bindings compare equal.
    return tuple(kind for kind in SESSION_KINDS if kind in kinds)


def describe_kinds(kinds: Iterable[str]) -> str:
    """Render kinds for a message: 'chat', 'resource generation', or both."""
    labels = [_LABELS.get(kind, kind) for kind in kinds]
    if len(labels) <= 1:
        return labels[0] if labels else "nothing"
    return " and ".join(labels)


def kinds_for(session_id: str) -> Tuple[str, ...]:
    """
    What a session was opened for, or () if it has no PDF bound.

    A binding written before this file existed has no `kinds` field. Those are treated as
    permitting everything rather than nothing: an old session is a session that worked,
    and breaking it to enforce a rule added later would be the wrong trade.
    """
    bound = content_store.get_session(session_id)
    if not bound:
        return ()
    return tuple(bound.get("kinds") or SESSION_KINDS)


def check_free(session_id: str, digest: str, filename: str) -> None:
    """
    Refuse a second, different PDF for a session that already has one.

    Embedding a document is the expensive step -- a few thousand chunks through a CPU
    embedding model -- so this runs before anything is stored or embedded, rather than
    letting the work start and cleaning up afterwards.

    Re-ingesting the *same* file is allowed: the bound hash is compared, not merely the
    presence of a binding, so `--force` can re-index a session's own PDF.
    """
    if not session_id or not config.ONE_PDF_PER_SESSION:
        return

    bound = content_store.get_session(session_id)
    if not bound or bound.get("sha256") == digest:
        return

    raise ValueError(
        f"Session {session_id!r} is already about {bound['filename']}. One PDF per "
        f"session -- ingest {filename} into a new session instead:\n"
        f"    python cli.py ingest {filename} --session <new-session-id>"
    )


def require_kind(session_id: str, kind: str) -> None:
    """
    Check a session was opened for the purpose it is now being used for.

    A no-op when there is no session or nothing bound to it -- commands run without a
    session fall back to the most recent document, and there is no stated intent to
    contradict.
    """
    if not session_id or kind not in SESSION_KINDS:
        return

    bound = content_store.get_session(session_id)
    if not bound:
        return

    allowed = kinds_for(session_id)
    if kind in allowed:
        return

    filename = bound.get("filename", "<pdf>")
    flag = "chat" if kind == "chat" else "resource"
    raise ValueError(
        f"Session {session_id!r} was opened for {describe_kinds(allowed)}, not "
        f"{_LABELS[kind]}.\n"
        f"Open one for {_LABELS[kind]} on the same PDF -- already ingested, so nothing "
        f"is re-embedded:\n"
        f"    python cli.py ingest {filename} --session <new-session-id> --for {flag}"
    )


def bind(session_id: str, doc_id, filename: str, digest: str,
         kinds: Tuple[str, ...], log=None) -> None:
    """Record which PDF a session is about and what it is for. No-op without a session."""
    if not session_id:
        return
    content_store.bind_session_document(session_id, doc_id, filename, digest, kinds)
    if log:
        log(f"[*] Session {session_id} -> {filename}  (for {describe_kinds(kinds)})")
