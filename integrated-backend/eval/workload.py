"""
A synthetic class: the questions students ask about the corpus, and when they ask them.

    python -m eval.workload generate [--chunks-per-doc 20] [--limit N] [--fake-llm]
    python -m eval.workload sessions [--students 40 --visits 3 --per-visit 4 --zipf 1.1]

`generate` (slow: one local-LLM call per sampled chunk) writes, per chunk, a *family*:

    seed        a question the chunk answers, in a student's words           (gold: chunk)
    para x2     two more wordings of the same question                       (gold: chunk)
    neg         a question on the same topic that needs a different answer   (hard negative)

This is the InPars / Promptagator recipe -- an LLM writes queries for sampled passages, and
the passage is the relevance label -- with two additions the cache evaluation needs:
paraphrases (which should share one cached answer) and near-miss negatives (which must
not). Generation is grammar-constrained JSON, so every call yields a usable record or is
retried; it is resumable, appending one line per chunk, because on a laptop CPU it runs
for an hour or two.

Known bias, and how it is handled: LLM-written questions borrow the passage's words, which
flatters lexical retrieval. The prompt asks for the student's own words, every record
stores its content-word overlap with the passage, and the paraphrases -- one step further
from the passage's wording -- are reported separately from the seeds.

`sessions` is deterministic and needs no model: 40 students each visit 3 times and ask 4
questions a visit over two weeks. Which question is Zipf-distributed over each document's
families (a few questions are what everyone asks), and which *wording* is drawn from the
family's seed and paraphrases -- students ask the same thing differently. A small share
of asks are the family's near-miss instead. Two pages per document are "planted" as
confusing: their families are more popular and more often asked again.
"""

import argparse
import json
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from eval.common import CORPUS_DIR, WORKLOAD_DIR, bootstrap, provenance, read_jsonl, \
    write_json, write_jsonl

FAMILIES = WORKLOAD_DIR / "families.jsonl"
QUESTIONS = WORKLOAD_DIR / "questions.jsonl"
SESSIONS = WORKLOAD_DIR / "sessions.jsonl"
MANIFEST = WORKLOAD_DIR / "manifest.json"

SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "paraphrases": {"type": "array", "items": {"type": "string"},
                        "minItems": 2, "maxItems": 2},
        "different_question": {"type": "string"},
    },
    "required": ["question", "paraphrases", "different_question"],
}

SYSTEM = ("You write the questions law students type into a study assistant while revising "
          "from their course notes. Students write casually and in their own words.")

PROMPT = """From the course notes "{title}":
\"\"\"
{chunk}
\"\"\"

Write JSON with:
- "question": one question a student might ask whose answer is in these notes. Use your
  own words; do not copy phrases from the notes.
- "paraphrases": two more ways other students might ask the SAME question, each worded
  differently from the others.
- "different_question": a question on the same topic that needs a DIFFERENT answer (for
  example, the opposite case, an exception, or a different element).
Every question must make sense on its own: no "the passage", "the notes" or "this"."""

_WORDS = re.compile(r"[a-z0-9]+")


def _content_overlap(question: str, chunk: str) -> float:
    """Share of the question's content terms that also appear in the chunk (stemmed)."""
    from learnmate.retrieval.analyzer import analyze

    terms = set(analyze(question))
    if not terms:
        return 0.0
    return len(terms & set(analyze(chunk))) / len(terms)


# "...according to the course notes?", "...that the notes mention?" -- the model citing the
# prompt back. A student asking the assistant about their notes does not say that.
_NOTE_REFS = re.compile(
    r"\s*,?\s*(?:(?:according to|as (?:discussed|described|mentioned|explained) in|"
    r"(?:mentioned|discussed|described) in|in|from|that)\s+)?(?:the|these|my|our)\s+"
    r"(?:course\s+)?notes(?:\s+(?:mention|describe|discuss|say))?", re.IGNORECASE)


def _strip_refs(text: str) -> str:
    return re.sub(r"\s+([?.!,])", r"\1", _NOTE_REFS.sub("", text or "")).strip()


def _clean(text: str) -> str:
    text = _strip_refs(re.sub(r"\s+", " ", (text or "").strip()))
    return text if text.endswith("?") else text.rstrip(".") + "?"


def _ok(text: str) -> bool:
    words = len(text.split())
    lower = text.lower()
    return 4 <= words <= 40 and not any(bad in lower for bad in
                                        ("the passage", "the notes", "the text above"))


def _sample_chunks(docs, per_doc: int, rng: random.Random):
    """Round-robin over pages so every part of a chapter is represented."""
    by_page = defaultdict(list)
    for doc in docs:
        text = doc.page_content or ""
        letters = sum(ch.isalpha() for ch in text)
        if len(text) >= 300 and letters / max(1, len(text)) > 0.6:
            by_page[doc.metadata["page_number"]].append(doc)
    for chunks in by_page.values():
        rng.shuffle(chunks)
    pages = sorted(by_page)
    picked = []
    while len(picked) < per_doc and any(by_page[p] for p in pages):
        for page in pages:
            if by_page[page] and len(picked) < per_doc:
                picked.append(by_page[page].pop())
    return picked


def _fake_llm(chunk_text: str):
    words = [w for w in _WORDS.findall(chunk_text.lower()) if len(w) > 5][:6] or ["law"]
    return {"question": f"What does {words[0]} mean in {words[-1]}?",
            "paraphrases": [f"Can you explain {words[0]} for {words[-1]}?",
                            f"How is {words[0]} defined here in {words[-1]}?"],
            "different_question": f"When does {words[0]} not apply to {words[-1]}?"}


def generate(per_doc: int, seed: int, limit: int = None, fake: bool = False) -> None:
    from langchain_core.messages import HumanMessage, SystemMessage

    from learnmate.llm import get_generator_llm
    from learnmate.storage import bm25_store

    manifest = json.loads((CORPUS_DIR / "corpus.json").read_text(encoding="utf-8"))
    done = {row["family_id"] for row in read_jsonl(FAMILIES)}
    llm = None if fake else get_generator_llm(temperature=0.5, max_tokens=320)
    rng = random.Random(seed)
    made = 0
    WORKLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with FAMILIES.open("a", encoding="utf-8") as out:
        for entry in manifest["documents"]:
            chunks = _sample_chunks(bm25_store.load_documents(entry["doc_id"]), per_doc, rng)
            for doc in chunks:
                meta = doc.metadata
                family_id = f"c{entry['chapter']:02d}-p{meta['page_number']}-k{meta['chunk_index']}"
                if family_id in done:
                    continue
                if limit is not None and made >= limit:
                    return
                started = time.perf_counter()
                record = None
                for attempt in range(3):
                    if fake:
                        data = _fake_llm(doc.page_content)
                    else:
                        reply = llm.invoke([
                            SystemMessage(content=SYSTEM),
                            HumanMessage(content=PROMPT.format(title=entry["title"],
                                                               chunk=doc.page_content))],
                            response_schema=SCHEMA)
                        try:
                            data = json.loads(reply.content)
                        except ValueError:
                            continue
                    question = _clean(data.get("question", ""))
                    paras = [_clean(p) for p in data.get("paraphrases", [])][:2]
                    negative = _clean(data.get("different_question", ""))
                    texts = [question] + paras + [negative]
                    if all(_ok(t) for t in texts) and len({t.lower() for t in texts}) == 4:
                        record = {
                            "family_id": family_id,
                            "doc_id": entry["doc_id"], "chapter": entry["chapter"],
                            "split": entry["split"],
                            "gold_page": meta["page_number"],
                            "gold_chunk": meta["chunk_index"],
                            "gold_key": f"{meta['page_number']}:{meta['chunk_index']}",
                            "seed": question, "paraphrases": paras, "negative": negative,
                            "overlap": {"seed": round(_content_overlap(question,
                                                                        doc.page_content), 3),
                                        "paraphrases": [round(_content_overlap(
                                            p, doc.page_content), 3) for p in paras]},
                            "attempts": attempt + 1,
                            "gen_s": round(time.perf_counter() - started, 1),
                        }
                        break
                if record is None:
                    print(f"  [!] {family_id}: no usable questions after 3 tries")
                    continue
                out.write(json.dumps(record) + "\n")
                out.flush()
                made += 1
                print(f"  {family_id} ({record['gen_s']}s): {record['seed']}")


# Questions that point at the book's structure ("...covered in chapter 5.2?") rather than
# its content: a student asking about their notes does not know the section numbering of
# the textbook they were cut from. Their whole family is dropped, and counted.
_STRUCTURE_REF = re.compile(r"\b(chapter|section)\s*\d|\bin (the|this) chapter\b",
                            re.IGNORECASE)


def flatten() -> list:
    """families.jsonl -> questions.jsonl: one row per wording, with its role."""
    rows, dropped = [], 0
    for family in read_jsonl(FAMILIES):
        texts = [family["seed"], *family["paraphrases"], family["negative"]]
        if any(_STRUCTURE_REF.search(text) for text in texts):
            dropped += 1
            continue
        base = {key: family[key] for key in ("family_id", "doc_id", "chapter", "split",
                                             "gold_page", "gold_chunk", "gold_key")}
        rows.append({**base, "qid": f"{family['family_id']}/s", "variant": "seed",
                     "text": _clean(family["seed"]), "overlap": family["overlap"]["seed"]})
        for i, text in enumerate(family["paraphrases"]):
            rows.append({**base, "qid": f"{family['family_id']}/p{i}", "variant": "para",
                         "text": _clean(text),
                         "overlap": family["overlap"]["paraphrases"][i]})
        rows.append({**base, "qid": f"{family['family_id']}/n", "variant": "neg",
                     "text": _clean(family["negative"]), "overlap": None})
    write_jsonl(QUESTIONS, rows)
    write_json(WORKLOAD_DIR / "flatten.json", {"families_kept": len(rows) // 4,
                                               "families_dropped_structure_ref": dropped})
    return rows


def sessions(students: int, visits: int, per_visit: int, zipf_s: float, neg_rate: float,
             planted_per_doc: int, seed: int) -> None:
    rng = random.Random(seed)
    rows = read_jsonl(QUESTIONS)
    families = defaultdict(list)
    for row in rows:
        families[row["family_id"]].append(row)
    by_doc = defaultdict(list)
    for family_id, members in families.items():
        by_doc[members[0]["doc_id"]].append(family_id)

    # Planted confusing pages: the pages of a document whose families get a popularity
    # boost and a higher chance of being asked again.
    planted, weights = {}, {}
    for doc_id, fams in by_doc.items():
        fams.sort()
        pages = sorted({families[f][0]["gold_page"] for f in fams})
        planted[doc_id] = sorted(rng.sample(pages, min(planted_per_doc, len(pages))))
        order = fams[:]
        rng.shuffle(order)
        for rank, family_id in enumerate(order, start=1):
            boost = 3.0 if families[family_id][0]["gold_page"] in planted[doc_id] else 1.0
            weights[family_id] = boost / rank ** zipf_s

    docs = sorted(by_doc)
    start = datetime(2026, 9, 1, 8, tzinfo=timezone.utc)
    out = []
    for student in range(students):
        # Each student studies two of the chapters, as a class does in a fortnight.
        mine = rng.sample(docs, min(2, len(docs)))
        asked = []
        for visit in range(visits):
            when = start + timedelta(days=rng.uniform(0, 14))
            doc_id = mine[visit % len(mine)]
            fams = by_doc[doc_id]
            for q in range(per_visit):
                # Coming back to something already asked -- more likely on planted pages.
                previous = [f for f in asked if families[f][0]["doc_id"] == doc_id]
                repeat_p = 0.15 + 0.25 * any(
                    families[f][0]["gold_page"] in planted[doc_id] for f in previous)
                if previous and rng.random() < repeat_p:
                    family_id = rng.choice(previous)
                else:
                    family_id = rng.choices(fams, weights=[weights[f] for f in fams])[0]
                asked.append(family_id)
                members = families[family_id]
                if rng.random() < neg_rate:
                    choice = next(m for m in members if m["variant"] == "neg")
                else:
                    choice = rng.choice([m for m in members if m["variant"] != "neg"])
                out.append({"student": f"student-{student:02d}", "visit": visit,
                            "t": (when + timedelta(minutes=3 * q)).isoformat(),
                            "doc_id": doc_id, "qid": choice["qid"],
                            "family_id": family_id, "variant": choice["variant"]})
    out.sort(key=lambda row: row["t"])
    write_jsonl(SESSIONS, out)
    write_json(MANIFEST, {"students": students, "visits": visits, "per_visit": per_visit,
                          "zipf_s": zipf_s, "neg_rate": neg_rate, "seed": seed,
                          "planted_pages": planted, "n_asks": len(out),
                          "n_families": len(families), "provenance": provenance()})
    print(f"[+] {len(out)} asks by {students} students over {len(docs)} documents")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the synthetic class workload.")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--chunks-per-doc", type=int, default=20)
    gen.add_argument("--seed", type=int, default=13)
    gen.add_argument("--limit", type=int, default=None)
    gen.add_argument("--fake-llm", action="store_true")
    sub.add_parser("flatten")
    ses = sub.add_parser("sessions")
    ses.add_argument("--students", type=int, default=40)
    ses.add_argument("--visits", type=int, default=3)
    ses.add_argument("--per-visit", type=int, default=4)
    ses.add_argument("--zipf", type=float, default=1.1)
    ses.add_argument("--neg-rate", type=float, default=0.1)
    ses.add_argument("--planted", type=int, default=2)
    ses.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    bootstrap()
    if args.command in ("generate", "flatten"):
        if args.command == "generate":
            generate(args.chunks_per_doc, args.seed, args.limit, args.fake_llm)
        rows = flatten()
        print(f"[+] {len(rows)} questions in {QUESTIONS}")
    else:
        if not QUESTIONS.exists():
            flatten()
        sessions(args.students, args.visits, args.per_visit, args.zipf, args.neg_rate,
                 args.planted, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
