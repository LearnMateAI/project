"""
LearnMate command line.

    python cli.py doctor                                   check models, MongoDB, config
    python cli.py ingest constitution.pdf --session s1      store + index one PDF
    python cli.py chat --session s1                        chat about that session's PDF
    python cli.py docs                                     list ingested documents
    python cli.py generate mcq --session s1 --count 5
    python cli.py generate summary --session s1 --topic "fundamental rights"
    python cli.py resources --task mcq                     show what has been generated
    python cli.py stats                                    evaluation score distribution
    python cli.py export <doc_id> ./out                    write a stored PDF back to disk

A session is about exactly one PDF, up to LEARNMATE_MAX_PDF_MB (10 MB by default).
Ingesting a second, different PDF into the same session is refused -- embedding a document
is the expensive step, so a new PDF means a new session id. `ingest` prints the session to
use when none is given. `--doc` overrides the session's PDF for one command.

Run `python cli.py <command> --help` for the options of any one command.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from learnmate import config
from learnmate.chat_agent import ChatAgent
from learnmate.ingestion import build_source_text, ingest_pdf
from learnmate.resource_agent import TASK_NAMES, generate_resource, render
from learnmate.storage import (
    QdrantUnavailable,
    StorageUnavailable,
    build_vector_store,
    content_store,
    export_pdf,
    list_documents,
    list_resources,
    pdf_store,
)

RULE = "=" * 68


def _resolve_doc(reference, session=None, required=True):
    """
    Work out which document a command is about.

    Three sources, most specific first:

        --doc       an explicit id, filename or fragment
        --session   the PDF that session was bound to at ingest time
        neither     the most recently ingested PDF

    The session path is the normal one: a session holds exactly one PDF, so `chat
    --session s1` never has to be told which document it means.
    """
    if not reference:
        document = pdf_store.get_document(content_store.session_doc_id(session)) \
            if session else None
        document = document or pdf_store.get_active_document()
        if document:
            return document
        if required:
            raise SystemExit("No PDF ingested yet. Run: python cli.py ingest <file.pdf>")
        return None

    document = pdf_store.resolve_document(reference)
    if not document:
        raise SystemExit(f"No document matches {reference!r}. "
                         "Run `python cli.py docs` to list them.")
    return document


# --- Commands ------------------------------------------------------------------------

def cmd_doctor(args):
    """Check every external dependency before anything slow is attempted."""
    from learnmate.storage.mongo import get_db

    print(RULE)
    print("LearnMate environment check")
    print(RULE)

    ok = True

    print("\nModels")
    for label, backend, path in (
        ("generator", config.GENERATOR_BACKEND, config.GENERATOR_MODEL),
        ("judge", config.JUDGE_BACKEND, config.JUDGE_MODEL),
    ):
        if backend == "http":
            print(f"  {label:10} http backend -> {path}")
            continue
        exists = Path(path).exists()
        size = f"{Path(path).stat().st_size / 1_073_741_824:.1f} GB" if exists else "MISSING"
        print(f"  {label:10} {'ok ' if exists else '!! '}{path}  ({size})")
        if not exists:
            print(f"             will be downloaded from HF on first use")

    print("\nMongoDB  (PDFs, page text, resources, evaluations, history)")
    try:
        database = get_db()
        server = database.client.server_info()
        print(f"  ok   {config.MONGODB_URI}  (server {server['version']}, db "
              f"{config.MONGODB_DB})")
        print(f"       documents={database[config.COLL_DOCUMENTS].count_documents({})} "
              f"pages={database[config.COLL_PAGES].count_documents({})} "
              f"resources={database[config.COLL_RESOURCES].count_documents({})}")
    except StorageUnavailable as exc:
        ok = False
        print(f"  !!   {exc}")

    print(f"\nVector database  (backend: {config.VECTOR_BACKEND})")
    try:
        store = build_vector_store()
        print(f"  ok   {store.describe_backend()}")
        print(f"       vectors={store.count()}")
    except QdrantUnavailable as exc:
        ok = False
        print(f"  !!   {exc}")
    except StorageUnavailable as exc:
        ok = False
        print(f"  !!   {exc}")
    except Exception as exc:
        ok = False
        print(f"  !!   {type(exc).__name__}: {exc}")

    print("\nSettings")
    print(f"  upload limit        {config.MAX_PDF_MB:g} MB per PDF"
          + ("  (one PDF per session)" if config.ONE_PDF_PER_SESSION else ""))
    print(f"  embeddings          {config.EMBEDDING_MODEL}")
    print(f"  chunk size/overlap  {config.CHUNK_SIZE}/{config.CHUNK_OVERLAP}")
    print(f"  relevance threshold {config.RELEVANCE_THRESHOLD}")
    print(f"  judge threshold     {config.EVALUATOR_THRESHOLD}")
    print(f"  max attempts        {config.MAX_ATTEMPTS}")
    print(RULE)
    return 0 if ok else 1


def cmd_ingest(args):
    # A session is generated when none is given, so every ingest is bound to something
    # and the one-PDF-per-session rule has an id to hold on to. It is printed below
    # because the user needs it to chat about what they just ingested.
    session = args.session or f"cli-{uuid.uuid4().hex[:12]}"

    report = ingest_pdf(args.path, session_id=session, force=args.force)
    document = report["document"]
    print(f"    id={document['_id']}  pages={report['n_pages']}  "
          f"chunks={report['n_chunks']}")
    print(f"\n    chat about it with:  python cli.py chat --session {session}")
    return 0


def cmd_docs(args):
    documents = list_documents(limit=args.limit)
    if not documents:
        print("No documents ingested yet. Try: python cli.py ingest <file.pdf>")
        return 0

    print(f"{'id':26} {'pages':>6} {'chunks':>7}  filename")
    print("-" * 68)
    for document in documents:
        print(f"{str(document['_id']):26} {str(document.get('n_pages') or '-'):>6} "
              f"{str(document.get('n_chunks') or '-'):>7}  {document['filename']}")
    return 0


def cmd_chat(args):
    document = _resolve_doc(args.doc, session=args.session, required=False)
    doc_id = document["_id"] if document else None

    agent = ChatAgent(
        session_id=args.session,
        doc_id=doc_id,
        threshold=args.threshold,
        evaluate=not args.no_eval,
        verbose=not args.quiet,
    )

    print(RULE)
    scope = document["filename"] if document else "the whole corpus"
    print(f"LearnMate chat  |  scope: {scope}  |  session: {agent.session_id}")
    print("Type 'exit' to stop, 'reset' to clear this session's history.")
    print(RULE)

    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            print("Bye.")
            return 0
        if query.lower() == "reset":
            print(f"Cleared {agent.reset()} turns.")
            continue

        result = agent.ask(query)

        print("\n--- Answer ---")
        print(result["reply"] or "(no answer produced)")

        if result["mode"] == "pdf":
            print("\n--- Sources ---")
            for i, (doc, score) in enumerate(zip(result["contexts"], result["scores"]), 1):
                print(f"  [{i}] {doc.metadata.get('filename', '?')} "
                      f"p.{doc.metadata.get('page_number')} (score {score:.4f})")
        else:
            print(f"\n--- Sources ---\n  general knowledge "
                  f"(best retrieval score {result['top_score']:.4f} "
                  f"< {config.RELEVANCE_THRESHOLD})")

        verdict = result["verdict"]
        if verdict:
            trail = " -> ".join(str(a["verdict"]["score"]) for a in result["attempts"]
                                if a.get("verdict"))
            status = "accepted" if result["accepted"] else "BELOW THRESHOLD (shown anyway)"
            print(f"\n--- Evaluation ---\n  {verdict['score']}/100 "
                  f"(threshold {verdict['threshold']}) - {status}")
            if len(result["attempts"]) > 1:
                print(f"  regenerated once, scores: {trail}")
            print(f"  {verdict['reasoning']}")
            if not result["accepted"] and verdict.get("regeneration_instruction"):
                print(f"  unresolved: {verdict['regeneration_instruction']}")


def cmd_generate(args):
    document = _resolve_doc(args.doc, session=args.session)

    source = build_source_text(document["_id"], topic=args.topic,
                               pages=args.pages, max_chars=args.max_source_chars)
    print(f"[*] Source: {len(source)} chars from {document['filename']}"
          + (f" matching {args.topic!r}" if args.topic else ""))

    result = generate_resource(
        args.task, source, count=args.count, doc_id=document["_id"],
        threshold=args.threshold, evaluate=not args.no_eval, verbose=not args.quiet,
    )

    if args.json:
        print(json.dumps({"task": result["task"], "content": result["content"],
                          "accepted": result["accepted"],
                          "resource_id": result["resource_id"]},
                         indent=2, ensure_ascii=False))
        return 0 if result["accepted"] else 1

    print("\n" + RULE)
    print(render(args.task, result["content"]) or "(nothing generated)")
    print(RULE)

    verdict = result["verdict"]
    if verdict:
        status = "accepted" if result["accepted"] else "BELOW THRESHOLD (shown anyway)"
        print(f"Score {verdict['score']}/100 (threshold {verdict['threshold']}) - {status}")
        print(f"Reasoning: {verdict['reasoning']}")
        if not result["accepted"] and verdict.get("regeneration_instruction"):
            print(f"Unresolved: {verdict['regeneration_instruction']}")
    elif result["attempts"]:
        last = result["attempts"][-1]
        if last["stage"] in ("validator", "parse"):
            print(f"Rejected by the {last['stage']} gate: {'; '.join(last['reasons'])}")

    if result["resource_id"]:
        print(f"Stored as resource {result['resource_id']}")
    return 0 if result["accepted"] else 1


def cmd_resources(args):
    document = _resolve_doc(args.doc, required=False)
    records = list_resources(doc_id=document["_id"] if document else None,
                             task=args.task, accepted_only=args.accepted,
                             limit=args.limit)
    if not records:
        print("No generated resources match.")
        return 0

    for record in records:
        stamp = record["created_at"].strftime("%Y-%m-%d %H:%M")
        score = record.get("score")
        flag = "PASS" if record["accepted"] else "fail"
        print(f"\n{RULE}\n{record['task']:13} {stamp}  "
              f"score={score if score is not None else '-':<5} {flag}  "
              f"attempts={record['n_attempts']}  id={record['_id']}")
        if args.show:
            print(RULE)
            print(render(record["task"], record["content"]))
    return 0


def cmd_stats(args):
    stats = content_store.evaluation_stats()
    stages = content_store.stage_counts()

    if not stats and not stages:
        print("No evaluations recorded yet.")
        return 0

    print(RULE)
    print("Which gate decided each attempt")
    print(RULE)
    for stage, count in sorted(stages.items(), key=lambda kv: -kv[1]):
        print(f"  {stage:12} {count}")

    if stats:
        print("\n" + RULE)
        print("Judge score distribution")
        print(RULE)
        print(f"{'task':14} {'n':>4} {'min':>4} {'med':>4} {'max':>4} {'mean':>6} "
              f"{'distinct':>9} {'pass':>6}")
        for task, row in stats.items():
            print(f"{task:14} {row['n']:>4} {row['min']:>4} {row['median']:>4} "
                  f"{row['max']:>4} {row['mean']:>6} {row['distinct']:>9} "
                  f"{row['pass_rate']:>6}")
        print("\nA narrow `distinct` range means the judge cannot separate good from bad")
        print("at any threshold; that is a rubric problem, not a threshold problem.")
    return 0


def cmd_export(args):
    document = _resolve_doc(args.doc)
    written = export_pdf(document["_id"], args.destination)
    print(f"[+] Wrote {written}")
    return 0


def cmd_delete(args):
    document = _resolve_doc(args.doc)
    confirm = input(f"Delete {document['filename']} and all its chunks? [y/N] ").strip()
    if confirm.lower() != "y":
        print("Cancelled.")
        return 1
    pdf_store.delete_document(document["_id"])
    print(f"[+] Deleted {document['filename']}")
    return 0


# --- Parser --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="LearnMate: ingest PDFs, chat about them, generate study resources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="check models, MongoDB and settings")
    doctor.set_defaults(func=cmd_doctor)

    ingest = subparsers.add_parser(
        "ingest", help=f"store and index one PDF (max {config.MAX_PDF_MB:g} MB)")
    ingest.add_argument("path", help="the PDF to ingest")
    ingest.add_argument("--session", help="bind the PDF to this session; "
                                          "omit to start a new one")
    ingest.add_argument("--force", action="store_true",
                        help="re-index even if this same PDF is already stored")
    ingest.set_defaults(func=cmd_ingest)

    docs = subparsers.add_parser("docs", help="list ingested documents")
    docs.add_argument("--limit", type=int, default=50)
    docs.set_defaults(func=cmd_docs)

    chat = subparsers.add_parser("chat", help="ask questions about a document")
    chat.add_argument("--doc", help="document id, filename, or fragment; "
                                    "omit to use the session's PDF")
    chat.add_argument("--session", help="the session to resume; its PDF is the scope")
    chat.add_argument("--threshold", type=int, default=None)
    chat.add_argument("--no-eval", action="store_true",
                      help="skip evaluation and the retry loop (much faster)")
    chat.add_argument("--quiet", action="store_true", help="hide per-node progress")
    chat.set_defaults(func=cmd_chat)

    generate = subparsers.add_parser("generate", help="generate a study resource")
    generate.add_argument("task", choices=TASK_NAMES)
    generate.add_argument("--doc", help="document id, filename, or fragment; "
                                        "omit to use the session's PDF")
    generate.add_argument("--session", help="generate from this session's PDF")
    generate.add_argument("--count", type=int, default=5,
                          help="items to produce (sentence budget for summary)")
    generate.add_argument("--topic", help="generate from the parts of the document most "
                                          "relevant to this topic")
    generate.add_argument("--pages", type=_page_list,
                          help="restrict the source to these pages, e.g. 3-7 or 2,5,9")
    generate.add_argument("--max-source-chars", type=int, default=config.MAX_SOURCE_CHARS)
    generate.add_argument("--threshold", type=int, default=None)
    generate.add_argument("--no-eval", action="store_true",
                          help="generate without the evaluator gates")
    generate.add_argument("--json", action="store_true", help="print raw JSON")
    generate.add_argument("--quiet", action="store_true")
    generate.set_defaults(func=cmd_generate)

    resources = subparsers.add_parser("resources", help="list generated resources")
    resources.add_argument("--doc")
    resources.add_argument("--task", choices=TASK_NAMES)
    resources.add_argument("--accepted", action="store_true", help="only ones that passed")
    resources.add_argument("--show", action="store_true", help="print the content too")
    resources.add_argument("--limit", type=int, default=10)
    resources.set_defaults(func=cmd_resources)

    stats = subparsers.add_parser("stats", help="evaluation score distribution")
    stats.set_defaults(func=cmd_stats)

    export = subparsers.add_parser("export", help="write a stored PDF back to disk")
    export.add_argument("doc")
    export.add_argument("destination")
    export.set_defaults(func=cmd_export)

    delete = subparsers.add_parser("delete", help="remove a document and its chunks")
    delete.add_argument("doc")
    delete.set_defaults(func=cmd_delete)

    return parser


def _page_list(value: str):
    """Parse `3-7` or `2,5,9` into a list of page numbers."""
    pages = []
    for part in value.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        elif part:
            pages.append(int(part))
    return pages


def main():
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (StorageUnavailable, QdrantUnavailable) as exc:
        print(f"\n[!] {exc}", file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f"\n[!] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
