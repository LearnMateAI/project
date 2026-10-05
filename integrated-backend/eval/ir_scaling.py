"""
How lexical retrieval's cost grows, in-process vs server-side.

    python -m eval.ir_scaling [--sizes 50 200 1000 3000] [--tenants 8 80 400]

Two experiments on synthetic copies of the eval corpus's real chunks (real text, real
vectors -- copied, not re-embedded):

  document size   one document of N chunks. The legacy in-process BM25 scores every chunk
                  of the document on every query, rebuilding each chunk's term counts as it
                  goes, and must first load and tokenise the whole document into each
                  process's memory (the cold start). Qdrant's sparse index answers from
                  posting lists. Measured: warm per-query latency of each, and the legacy
                  cold build.

  tenants         D documents of the usual size in one collection. Every query filters to
                  one document; with doc_id as a tenant key, a filtered search should not
                  grow with the documents it is not searching.

Written to their own collection (`eval_scale`) and to the eval database only.
"""

import argparse
import random
import sys
import time

from eval.common import WORKLOAD_DIR, bootstrap, provenance, read_jsonl, run_dir, write_json
from eval.metrics import latency_summary

COLLECTION = "eval_scale"


def _source_chunks():
    """Every eval chunk with its dense vector, from the eval collection."""
    from learnmate.storage.vectors import get_vector_store

    store = get_vector_store()
    return [(payload, vector) for payload, vector in store.scroll_points()]


def _build(store, bm25_store, doc_id: str, chunks, n: int):
    """Write a synthetic document of n chunks to Qdrant and to the BM25 sidecar."""
    from langchain_core.documents import Document

    texts, metas, dense, docs = [], [], [], []
    for i in range(n):
        payload, vector = chunks[i % len(chunks)]
        page, index = 1 + i // 4, i % 4
        texts.append(payload["text"])
        metas.append({"doc_id": doc_id, "page_number": page, "chunk_index": index,
                      "filename": f"{doc_id}.pdf"})
        dense.append(vector)
        docs.append(Document(page_content=payload["text"], metadata=metas[-1]))
    for start in range(0, n, 512):
        store.upsert_chunks(texts[start:start + 512], metas[start:start + 512],
                            dense[start:start + 512])
    bm25_store.index_documents(doc_id, docs)


def _time(fn, repeats: int):
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    return latency_summary(samples)


def run(sizes, tenants, queries_n: int, seed: int):
    from bson import ObjectId

    from learnmate.storage import bm25_store
    from learnmate.storage.qdrant_vectors import QdrantVectorStore

    rng = random.Random(seed)
    chunks = _source_chunks()
    questions = [q["text"] for q in read_jsonl(WORKLOAD_DIR / "questions.jsonl")
                 if q["variant"] == "seed"]
    queries = rng.sample(questions, min(queries_n, len(questions)))

    store = QdrantVectorStore(collection_name=COLLECTION, schema="v2")
    if store.client.collection_exists(COLLECTION):
        store.client.delete_collection(COLLECTION)
    store.ensure_collection()
    embed = store.embeddings.embed_query
    vectors = {q: embed(q) for q in queries}

    size_rows = []
    for n in sizes:
        doc_id = str(ObjectId())
        _build(store, bm25_store, doc_id, chunks, n)

        bm25_store.invalidate_cache(doc_id)
        started = time.perf_counter()
        index, _docs = bm25_store.get_okapi(doc_id)
        cold_ms = (time.perf_counter() - started) * 1000

        row = {"chunks": n, "legacy_cold_build_ms": cold_ms}
        row["legacy_bm25_ms"] = _time(
            lambda: [index.ranked(q, 10) for q in queries], 3)
        for strategy in ("bm25", "rrf", "dense"):
            row[f"qdrant_{strategy}_ms"] = _time(
                lambda s=strategy: [store.query(s, q, vectors[q], 20, doc_id=doc_id)
                                    for q in queries], 3)
        # Per query, not per batch of queries.
        for key in ("legacy_bm25_ms", "qdrant_bm25_ms", "qdrant_rrf_ms", "qdrant_dense_ms"):
            row[key] = {stat: (value / len(queries) if isinstance(value, float) else value)
                        for stat, value in row[key].items()}
        size_rows.append(row)
        print(f"  {n} chunks: legacy BM25 {row['legacy_bm25_ms']['p50']:.2f} ms/q "
              f"(cold {cold_ms:.0f} ms), qdrant bm25 {row['qdrant_bm25_ms']['p50']:.2f} ms/q")
        bm25_store.delete_for(doc_id)
        store.delete(doc_id=doc_id)

    tenant_rows = []
    made = []
    for d in tenants:
        while len(made) < d:
            doc_id = str(ObjectId())
            _build(store, bm25_store, doc_id, chunks, 43)
            made.append(doc_id)
        probes = rng.sample(made, min(10, len(made)))
        row = {"documents": d, "points": d * 43}
        for strategy in ("bm25", "rrf", "dense"):
            samples = []
            for doc_id in probes:
                for q in queries[:10]:
                    started = time.perf_counter()
                    store.query(strategy, q, vectors[q], 20, doc_id=doc_id)
                    samples.append((time.perf_counter() - started) * 1000)
            row[f"qdrant_{strategy}_ms"] = latency_summary(samples)
        tenant_rows.append(row)
        print(f"  {d} documents: rrf p50 {row['qdrant_rrf_ms']['p50']:.2f} ms")
    for doc_id in made:
        bm25_store.delete_for(doc_id)
    store.client.delete_collection(COLLECTION)
    return {"document_size": size_rows, "tenants": tenant_rows, "queries": len(queries)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sizes", nargs="+", type=int, default=[50, 200, 1000, 3000])
    parser.add_argument("--tenants", nargs="+", type=int, default=[8, 80, 400])
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    bootstrap()
    results = run(sorted(args.sizes), sorted(args.tenants), args.queries, args.seed)
    results["provenance"] = provenance()
    print(f"[+] {write_json(run_dir('ir') / 'ir_scaling.json', results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
