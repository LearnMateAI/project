"""
LearnMate end to end, in one terminal program.

    python full_program.py                 interactive menu
    python full_program.py --demo          run the whole workflow start to finish
    python full_program.py --pdf x.pdf --ask "..."    upload and ask one question
    python full_program.py --demo --no-eval          same, but skip the judge (faster)

Every package in learnmate/ is exercised, in the order the real system uses them:

    ingestion   a PDF path -> stored PDF, cleaned pages, chunks, embeddings, and a
                session bound to it
    storage     MongoDB holds the PDF, its page text and everything produced from it;
                Qdrant holds the chunk vectors
    llm         Qwen2.5-3B generates, Llama-3.2-3B judges, MiniLM embeds
    chat_agent  a question -> rewrite -> retrieve -> generate -> evaluate -> reply
    resource_agent + evaluator
                a passage -> mcq / summary / keypoints / practice_qsn, each through a
                structural gate and then the judge, with one retry

Both databases run in containers: `docker compose up -d` before starting this.

A note on speed. Everything runs locally on CPU, so a chat turn is roughly 20-60s and a
judged resource 60-120s. `--no-eval` skips the judge and roughly halves that, at the cost
of the quality gate. The first action of a session also loads ~4 GB of model weights.
"""

import argparse
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

# Works whether this is run from learnmate/ or from components-Dinura/: put the package's
# parent on the path so `import learnmate` resolves either way.
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))


def _use_project_venv() -> None:
    """
    Re-run under the project's virtualenv if this interpreter cannot import the deps.

    `python full_program.py` on a machine where `python` is the system interpreter fails
    deep inside an import chain with something like "No module named 'bson'", which says
    nothing about the real problem. Checking here turns that into either a silent
    hand-off to the right interpreter or one clear sentence.

    Guarded by an environment variable so a venv that is itself missing a dependency
    reports that honestly instead of looping.
    """
    if os.environ.get("LEARNMATE_VENV_REEXEC"):
        return  # already handed off once; let the real ImportError surface

    try:
        # Import the package itself rather than a hand-picked list of third-party names.
        # Guessing which dependency is missing gets it wrong -- an interpreter can have
        # pymongo but not langchain_text_splitters -- and this exercises the exact chain
        # that is about to run. It is free on success: Python caches the module.
        import learnmate  # noqa: F401
        return
    except ImportError as exc:
        missing = getattr(exc, "name", None) or "a dependency"

    candidates = [PROJECT / "venv" / "Scripts" / "python.exe",   # Windows
                  PROJECT / "venv" / "bin" / "python"]           # macOS / Linux
    venv_python = next((p for p in candidates if p.exists()), None)

    if venv_python is None:
        pip = "venv\\Scripts\\pip" if os.name == "nt" else "venv/bin/pip"
        print(
            f"This interpreter cannot import {missing}, and there is no virtualenv at "
            f"{PROJECT / 'venv'}.\n\n"
            "Create one and install the dependencies:\n"
            f"    cd {PROJECT}\n"
            "    python -m venv venv\n"
            f"    {pip} install -r requirements.txt\n",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # flush: this process's stdout is buffered until it exits, which is *after* the child
    # has finished, so without it the hand-off message prints last and reads as if the
    # switch happened at the end.
    print(f"[*] This interpreter cannot import {missing}; "
          f"switching to {venv_python}", flush=True)
    # subprocess rather than os.execv: it inherits stdin, so the interactive menu still
    # works, and it avoids Windows' argument-quoting quirks in exec.
    os.environ["LEARNMATE_VENV_REEXEC"] = "1"
    completed = subprocess.run([str(venv_python), str(Path(__file__).resolve()),
                                *sys.argv[1:]])
    raise SystemExit(completed.returncode)


_use_project_venv()

from learnmate import config
from learnmate.chat_agent import ChatAgent
from learnmate.ingestion import build_source_text, ingest_pdf
from learnmate.resource_agent import generate_resource, render
from learnmate.storage import (
    QdrantUnavailable,
    StorageUnavailable,
    build_vector_store,
    content_store,
    list_resources,
    pdf_store,
)

DEFAULT_PDF = HERE.parent / "data" / "raw_pdfs" / "constitution.pdf"
RULE = "=" * 74
THIN = "-" * 74

# What each task is called on screen, and a sensible count for it.
TASK_LABELS = {
    "mcq": ("Multiple-choice questions", 5),
    "summary": ("Summary", 5),
    "keypoints": ("Key points", 5),
    "practice_qsn": ("Short-answer practice questions", 4),
}
TASK_ORDER = ("mcq", "summary", "keypoints", "practice_qsn")


def banner(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


# --- Step 0: is the system actually ready? ---------------------------------------------

def preflight() -> bool:
    """
    Check both databases and both model files before anything slow is attempted.

    Worth doing first: without it, a missing Qdrant surfaces several minutes into an
    ingest, after the embedding model has already loaded.
    """
    banner("Checking the system")
    ready = True

    print("Models")
    for label, backend, path in (
        ("generator", config.GENERATOR_BACKEND, config.GENERATOR_MODEL),
        ("judge", config.JUDGE_BACKEND, config.JUDGE_MODEL),
    ):
        if backend == "http":
            print(f"  {label:10} served over HTTP -> {path}")
            continue
        exists = Path(path).exists()
        size = f"{Path(path).stat().st_size / 1_073_741_824:.1f} GB" if exists else "MISSING"
        print(f"  {label:10} {'ok  ' if exists else '!!  '}{Path(path).name}  ({size})")
        if not exists:
            print("             will be downloaded from Hugging Face on first use (~2 GB)")

    print("\nMongoDB   (PDFs, page text, sessions, history, resources, evaluations)")
    try:
        from learnmate.storage.mongo import get_db

        db = get_db()
        version = db.client.server_info()["version"]
        print(f"  ok   {config.MONGODB_URI}  (server {version}, db {config.MONGODB_DB})")
        print(f"       documents={db[config.COLL_DOCUMENTS].count_documents({})} "
              f"pages={db[config.COLL_PAGES].count_documents({})} "
              f"sessions={db[config.COLL_SESSIONS].count_documents({})} "
              f"resources={db[config.COLL_RESOURCES].count_documents({})}")
    except StorageUnavailable as exc:
        ready = False
        print(f"  !!   {exc}")

    print(f"\nVector database   (backend: {config.VECTOR_BACKEND})")
    try:
        store = build_vector_store()
        print(f"  ok   {store.describe_backend()}")
        print(f"       vectors={store.count()}")
    except (QdrantUnavailable, StorageUnavailable) as exc:
        ready = False
        print(f"  !!   {exc}")
    except Exception as exc:
        ready = False
        print(f"  !!   {type(exc).__name__}: {exc}")

    if not ready:
        print(f"\n{THIN}\nStart the databases with:  docker compose up -d\n{THIN}")
    return ready


# --- Step 1: upload a PDF --------------------------------------------------------------

def upload(pdf_path: Path, session_id: str = None, force: bool = False) -> dict:
    """
    Ingest one PDF and bind a session to it.

    A fresh session id per upload, because a session holds exactly one PDF -- reusing the
    id for a different file is refused by design. Bound `for="both"` so the same upload
    serves the chat agent and the resource generator without a second ingest.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"No such PDF: {pdf_path}")

    session_id = session_id or f"run-{uuid.uuid4().hex[:10]}"
    banner(f"Uploading {pdf_path.name}")
    print(f"path    {pdf_path}")
    print(f"size    {pdf_path.stat().st_size / 1_048_576:.2f} MB "
          f"(limit {config.MAX_PDF_MB:g} MB)")
    print(f"session {session_id}  (for chat and resource generation)\n")

    started = time.time()
    report = ingest_pdf(pdf_path, session_id=session_id, session_for="both", force=force)

    print(f"\n{'Already ingested' if report['skipped'] else 'Ingested'} in "
          f"{report['elapsed_s']}s (wall {time.time() - started:.1f}s)")
    print(f"  document id  {report['doc_id']}")
    print(f"  pages        {report['n_pages']}")
    print(f"  chunks       {report['n_chunks']}")
    return report


# --- Step 2: chat ----------------------------------------------------------------------

def show_chat_result(result: dict) -> None:
    """Print one chat turn: the reply, where it came from, and how it was graded."""
    print(f"\n{THIN}")
    print(result["reply"] or "(no answer produced)")
    print(THIN)

    if result.get("standalone_query") and result["standalone_query"] != result["query"]:
        print(f"rewritten as : {result['standalone_query']}")

    if result["mode"] == "pdf":
        print(f"mode         : PDF (top retrieval score {result['top_score']:.4f})")
        for i, (doc, score) in enumerate(zip(result["contexts"], result["scores"]), 1):
            preview = " ".join(doc.page_content.split())[:58]
            print(f"  [{i}] p.{str(doc.metadata.get('page_number')):<4} "
                  f"{score:.4f}  {preview}...")
    else:
        print(f"mode         : general knowledge "
              f"(best score {result['top_score']:.4f} < {config.RELEVANCE_THRESHOLD})")

    verdict = result.get("verdict")
    if verdict:
        status_text = "accepted" if result["accepted"] else "BELOW THRESHOLD (shown anyway)"
        print(f"evaluation   : {verdict['score']}/100 "
              f"(threshold {verdict['threshold']}) - {status_text}")
        if len(result["attempts"]) > 1:
            trail = " -> ".join(str(a["verdict"]["score"]) for a in result["attempts"]
                                if a.get("verdict"))
            print(f"               regenerated once, scores: {trail}")
        print(f"               {verdict['reasoning']}")


def ask_once(agent: ChatAgent, question: str) -> dict:
    """One question through the chat graph, timed."""
    print(f"\nYou: {question}")
    started = time.time()
    result = agent.ask(question)
    show_chat_result(result)
    print(f"took         : {time.time() - started:.1f}s")
    return result


def chat_loop(agent: ChatAgent) -> None:
    """Interactive chat until the user leaves."""
    banner(f"Chat  |  session {agent.session_id}")
    print("Ask anything about the PDF. Commands: 'history', 'reset', 'back'.")

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not question:
            continue
        low = question.lower()
        if low in ("back", "exit", "quit"):
            return
        if low == "reset":
            print(f"Cleared {agent.reset()} turns.")
            continue
        if low == "history":
            turns = agent.history()
            if not turns:
                print("  (nothing yet)")
            for turn in turns:
                print(f"  {turn['role']:9} {turn['content'][:80]}")
            continue

        started = time.time()
        try:
            show_chat_result(agent.ask(question))
            print(f"took         : {time.time() - started:.1f}s")
        except Exception as exc:
            print(f"  [!] {type(exc).__name__}: {exc}")


# --- Step 3: generate resources --------------------------------------------------------

def make_resource(task: str, doc_id, topic: str = None, count: int = None,
                  evaluate: bool = True, quiet: bool = False) -> dict:
    """
    Generate one resource and print it with its verdict.

    The passage comes from ingestion.build_source_text: with a topic it is the pages that
    best match it, otherwise the opening of the document up to the budget.
    """
    label, default_count = TASK_LABELS[task]
    count = count or default_count

    banner(f"{label}  ({task})")

    source = build_source_text(doc_id, topic=topic)
    print(f"source  : {len(source)} chars from the document"
          + (f", matching {topic!r}" if topic else " (opening pages)"))
    print(f"asking  : {count} {'sentences' if task == 'summary' else 'items'}"
          f"   evaluation: {'on' if evaluate else 'off'}\n")

    started = time.time()
    result = generate_resource(task, source, count=count, doc_id=doc_id,
                               evaluate=evaluate, verbose=not quiet)

    print(f"\n{THIN}")
    print(render(task, result["content"]) or "(nothing generated)")
    print(THIN)

    verdict = result.get("verdict")
    if verdict:
        status_text = "accepted" if result["accepted"] else "BELOW THRESHOLD (shown anyway)"
        print(f"score    : {verdict['score']}/100 "
              f"(threshold {verdict['threshold']}) - {status_text}")
        print(f"reasoning: {verdict['reasoning']}")
    elif result["attempts"]:
        # No verdict means a cheaper gate decided it, or no gate ran at all.
        last = result["attempts"][-1]
        if last.get("stage") in ("validator", "parse"):
            print(f"rejected by the {last['stage']} gate: "
                  f"{'; '.join(last.get('reasons', []))}")
        elif last.get("stage") == "skipped":
            # `accepted` is True here only because nothing graded it. Saying so matters:
            # unevaluated output looks identical to output that passed.
            print("score    : not evaluated (--no-eval). Nothing checked this content "
                  "for faithfulness to the passage.")

    print(f"attempts : {len(result['attempts'])}   "
          f"stored as: {result['resource_id']}   took {time.time() - started:.1f}s")
    return result


def all_resources(doc_id, topic: str = None, evaluate: bool = True,
                  quiet: bool = False) -> dict:
    """Generate all four kinds and summarise how each fared."""
    results = {}
    for task in TASK_ORDER:
        try:
            results[task] = make_resource(task, doc_id, topic=topic, evaluate=evaluate,
                                          quiet=quiet)
        except Exception as exc:
            print(f"  [!] {task} failed: {type(exc).__name__}: {exc}")
            results[task] = None

    banner("Resource summary")
    print(f"{'task':16} {'verdict':>14} {'score':>6} {'attempts':>9}  stored")
    print(THIN)
    for task, result in results.items():
        if result is None:
            print(f"{task:16} {'ERROR':>14}")
            continue
        verdict = result.get("verdict") or {}
        score = verdict.get("score")
        # Without a verdict there was no judge, so `accepted` only means "nothing
        # objected". Reporting that as "accepted" would overstate it badly.
        label = ("accepted" if result["accepted"] else "below threshold") if verdict \
            else "not evaluated"
        print(f"{task:16} {label:>14} "
              f"{str(score if score is not None else '-'):>6} "
              f"{len(result['attempts']):>9}  {result['resource_id']}")

    if not evaluate:
        print("\nEvaluation was off, so none of this was checked for faithfulness to the")
        print("passage. Re-run without --no-eval (or press 'e' in the menu) to grade it.")
    return results


# --- Status ----------------------------------------------------------------------------

def show_status(doc_id=None, session_id: str = None) -> None:
    """What is currently stored, across both databases."""
    banner("Stored state")

    documents = pdf_store.list_documents(limit=10)
    print(f"Documents ({len(documents)})")
    for document in documents:
        marker = " <-- this run" if doc_id and document["_id"] == doc_id else ""
        print(f"  {str(document['_id'])}  {str(document.get('n_pages') or '-'):>4}p "
              f"{str(document.get('n_chunks') or '-'):>5}c  {document['filename']}{marker}")

    if session_id:
        bound = content_store.get_session(session_id)
        print(f"\nSession {session_id}")
        if bound:
            print(f"  PDF   {bound['filename']}")
            print(f"  for   {', '.join(bound.get('kinds') or [])}")
            print(f"  turns {len(content_store.load_history(session_id, max_turns=999))}")
        else:
            print("  (no PDF bound yet)")

    if doc_id:
        records = list_resources(doc_id=doc_id, limit=10)
        print(f"\nGenerated resources for this document ({len(records)})")
        for record in records:
            print(f"  {record['task']:14} score={str(record.get('score') or '-'):>4} "
                  f"{'PASS' if record['accepted'] else 'fail'}  {record['_id']}")

    try:
        store = build_vector_store()
        print(f"\nVectors: {store.count()} total"
              + (f", {store.count(doc_id)} for this document" if doc_id else ""))
    except Exception as exc:
        print(f"\nVectors: unavailable ({type(exc).__name__})")


# --- Interactive menu ------------------------------------------------------------------

class Session:
    """Everything the menu needs to remember between choices."""

    def __init__(self):
        self.doc_id = None
        self.session_id = None
        self.filename = None
        self.evaluate = True
        self.topic = None

    @property
    def ready(self) -> bool:
        return self.doc_id is not None

    def agent(self) -> ChatAgent:
        # `evaluate` has to be passed through, or the menu's toggle would silently apply
        # to resource generation only and chat would always pay for the judge.
        return ChatAgent(session_id=self.session_id, doc_id=self.doc_id,
                         evaluate=self.evaluate)


def prompt_pdf(state: Session) -> None:
    """Ask for a PDF path and ingest it."""
    default = DEFAULT_PDF if DEFAULT_PDF.exists() else None
    hint = f" [{default}]" if default else ""
    raw = input(f"\nPDF file path{hint}: ").strip().strip('"')
    path = Path(raw) if raw else default

    if path is None:
        print("  A path is required.")
        return

    try:
        report = upload(path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"  [!] {exc}")
        return

    state.doc_id = report["document"]["_id"]
    state.session_id = report["session_id"]
    state.filename = report["document"]["filename"]


def menu(state: Session) -> None:
    """The main loop."""
    while True:
        banner("LearnMate")
        if state.ready:
            print(f"PDF        : {state.filename}")
            print(f"session    : {state.session_id}")
            print(f"topic      : {state.topic or '(whole document)'}")
        else:
            print("No PDF uploaded yet.")
        print(f"evaluation : {'on' if state.evaluate else 'off'}")

        print(f"\n{THIN}")
        print("  1  Upload a PDF")
        print("  2  Chat about it")
        print("  3  Generate MCQs")
        print("  4  Generate a summary")
        print("  5  Generate key points")
        print("  6  Generate practice questions")
        print("  7  Generate all four")
        print("  8  Show stored state")
        print("  9  Set a topic for generation")
        print("  e  Toggle evaluation (the judge and its retry)")
        print("  0  Quit")
        print(THIN)

        try:
            choice = input("Choose: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return

        if choice == "0":
            print("Bye.")
            return
        if choice == "1":
            prompt_pdf(state)
            continue
        if choice == "e":
            state.evaluate = not state.evaluate
            continue
        if choice == "9":
            raw = input("Topic (blank for the whole document): ").strip()
            state.topic = raw or None
            continue

        # Everything below needs a document.
        if not state.ready and choice in ("2", "3", "4", "5", "6", "7", "8"):
            print("\n  Upload a PDF first (option 1).")
            continue

        try:
            if choice == "2":
                chat_loop(state.agent())
            elif choice in ("3", "4", "5", "6"):
                task = {"3": "mcq", "4": "summary", "5": "keypoints",
                        "6": "practice_qsn"}[choice]
                make_resource(task, state.doc_id, topic=state.topic,
                              evaluate=state.evaluate)
            elif choice == "7":
                all_resources(state.doc_id, topic=state.topic, evaluate=state.evaluate)
            elif choice == "8":
                show_status(state.doc_id, state.session_id)
            else:
                print("  Unknown choice.")
        except KeyboardInterrupt:
            print("\n  Interrupted.")
        except Exception as exc:
            print(f"\n  [!] {type(exc).__name__}: {exc}")


# --- Non-interactive modes -------------------------------------------------------------

def run_demo(pdf: Path, questions, topic: str, evaluate: bool, quiet: bool) -> int:
    """The whole workflow start to finish, with no prompts. Used to smoke-test a change."""
    report = upload(pdf)
    doc_id = report["document"]["_id"]
    session_id = report["session_id"]

    banner(f"Chat  |  session {session_id}")
    agent = ChatAgent(session_id=session_id, doc_id=doc_id, evaluate=evaluate,
                      verbose=not quiet)
    for question in questions:
        ask_once(agent, question)

    results = all_resources(doc_id, topic=topic, evaluate=evaluate, quiet=quiet)
    show_status(doc_id, session_id)

    banner("Done")
    failed = [t for t, r in results.items() if r is None]
    if failed:
        print(f"These resources errored: {', '.join(failed)}")
        return 1
    print("Every stage ran. Anything marked BELOW THRESHOLD was produced but not accepted")
    print("by the evaluator, which is a quality result rather than a failure.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LearnMate end to end: upload a PDF, chat about it, generate resources.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF,
                        help=f"PDF to ingest (default: {DEFAULT_PDF.name})")
    parser.add_argument("--ask", action="append", default=[],
                        help="ask this question; repeatable")
    parser.add_argument("--topic", help="focus resource generation on this topic")
    parser.add_argument("--demo", action="store_true",
                        help="run the whole workflow without prompting")
    parser.add_argument("--no-eval", action="store_true",
                        help="skip the judge and its retry (much faster)")
    parser.add_argument("--quiet", action="store_true", help="hide per-node progress")
    parser.add_argument("--skip-checks", action="store_true",
                        help="do not verify the databases and models first")
    args = parser.parse_args()

    if not args.skip_checks and not preflight():
        return 2

    try:
        # Non-interactive whenever the caller gave something to do.
        if args.demo or args.ask:
            questions = args.ask or [
                "What is this document about?",
                "What does it say about fundamental rights?",
            ]
            return run_demo(args.pdf, questions, args.topic,
                            evaluate=not args.no_eval, quiet=args.quiet)

        state = Session()
        state.evaluate = not args.no_eval
        state.topic = args.topic
        menu(state)
        return 0
    except (StorageUnavailable, QdrantUnavailable) as exc:
        print(f"\n[!] {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        # A missing PDF, one over the size limit, or a session that already holds a
        # different PDF. All are the user's to fix, so say so plainly rather than
        # printing a traceback at them.
        print(f"\n[!] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
