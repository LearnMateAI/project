"""
Build a v2 Qdrant collection (dense + BM25 sparse) from what is already stored.

    python scripts/reindex_qdrant.py                         # learnmate_chunks -> learnmate_chunks_v2
    python scripts/reindex_qdrant.py --target my_v2 --splade # also the learned-sparse ablation
    python scripts/reindex_qdrant.py --dry-run

Nothing is re-read from the PDFs and, by default, nothing is re-embedded. Chunk text comes
from MongoDB (`bm25_chunks`, which ingestion writes for every document), and each chunk's
dense vector is copied from the source collection. A chunk is re-embedded only when its
vector is missing or the document was embedded by a different model than is configured now.

The source collection is never modified. Switching over is two lines of .env, printed at
the end, and switching back is deleting them.

avgdl -- the average chunk length BM25 normalises against -- is measured over the whole
corpus first and stored in MongoDB (`retrieval_meta`), because every document vector
written after it depends on that one number.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learnmate import config  # noqa: E402
from learnmate.llm.embeddings import get_embeddings  # noqa: E402
from learnmate.retrieval.sparse import ANALYZER_VERSION, mean_doc_length  # noqa: E402
from learnmate.storage import bm25_store, retrieval_meta  # noqa: E402
from learnmate.storage.mongo import get_db  # noqa: E402
from learnmate.storage.qdrant_vectors import QdrantVectorStore  # noqa: E402


def _documents(only):
    query = {"processing_status": "Ready"}
    rows = list(get_db()[config.COLL_DOCUMENTS].find(
        query, {"filename": 1, "embedding_model": 1, "n_chunks": 1}))
    if only:
        wanted = set(only)
        rows = [row for row in rows if str(row["_id"]) in wanted]
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", default=config.QDRANT_COLLECTION)
    parser.add_argument("--target", default=None,
                        help="default: <source>_v2")
    parser.add_argument("--docs", nargs="*", help="only these document ids")
    parser.add_argument("--reembed", action="store_true",
                        help="embed every chunk again instead of copying vectors")
    parser.add_argument("--splade", action="store_true",
                        help="also build the learned-sparse vector (ablation)")
    parser.add_argument("--recreate", action="store_true",
                        help="drop the target collection first")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    target_name = args.target or f"{args.source}_v2"
    if target_name == args.source:
        print("[!] Target and source are the same collection; refusing.")
        return 2

    documents = _documents(args.docs)
    print(f"[*] {len(documents)} ready document(s) in MongoDB "
          f"{config.MONGODB_URI}/{config.MONGODB_DB}")

    corpus = {}
    for document in documents:
        chunks = bm25_store.ensure_index(document["_id"])
        corpus[str(document["_id"])] = chunks
        print(f"    {document.get('filename')!r}: {len(chunks)} chunks")

    all_texts = [doc.page_content for chunks in corpus.values() for doc in chunks]
    avgdl = config.BM25_AVGDL or mean_doc_length(all_texts)
    print(f"[*] {len(all_texts)} chunks, avgdl {avgdl:.1f} analyzed terms "
          f"({ANALYZER_VERSION}, k1={config.BM25_K1}, b={config.BM25_B})")
    if args.dry_run:
        return 0

    retrieval_meta.set_bm25_meta(avgdl, len(all_texts), ANALYZER_VERSION)

    embeddings = get_embeddings()
    source = QdrantVectorStore(collection_name=args.source)
    source_exists = source.client.collection_exists(args.source)
    target = QdrantVectorStore(collection_name=target_name, schema="v2",
                               splade=args.splade)
    if args.recreate and target.client.collection_exists(target_name):
        print(f"[*] Dropping {target_name!r}")
        target.client.delete_collection(target_name)
    target.ensure_collection()
    if target.schema != "v2":
        print(f"[!] {target_name!r} exists and is not a v2 collection; use --recreate.")
        return 2

    started = time.time()
    copied = embedded = 0
    for document in documents:
        doc_id = str(document["_id"])
        chunks = corpus[doc_id]
        if not chunks:
            continue

        vectors = {}
        same_model = document.get("embedding_model") in (None, config.EMBEDDING_MODEL)
        if source_exists and same_model and not args.reembed:
            for payload, vector in source.scroll_points(doc_id):
                if vector:
                    vectors[(payload.get("page_number"), payload.get("chunk_index"))] = vector

        missing = [doc for doc in chunks
                   if (doc.metadata.get("page_number"), doc.metadata.get("chunk_index"))
                   not in vectors]
        if missing:
            fresh = embeddings.embed_documents([doc.page_content for doc in missing])
            for doc, vector in zip(missing, fresh):
                vectors[(doc.metadata.get("page_number"),
                         doc.metadata.get("chunk_index"))] = vector
        copied += len(chunks) - len(missing)
        embedded += len(missing)

        metadatas = [{**doc.metadata, "doc_id": doc_id} for doc in chunks]
        dense = [vectors[(doc.metadata.get("page_number"), doc.metadata.get("chunk_index"))]
                 for doc in chunks]
        target.upsert_chunks([doc.page_content for doc in chunks], metadatas, dense)

        stored = target.count(doc_id)
        status = "ok" if stored == len(chunks) else f"MISMATCH ({stored} stored)"
        print(f"    {document.get('filename')!r}: {len(chunks)} chunks -> {status}")

    print(f"[+] Done in {time.time() - started:.1f}s: {copied} vectors copied, "
          f"{embedded} embedded.")
    print("\nTo switch the server over, add to .env:\n"
          f"    LEARNMATE_QDRANT_COLLECTION={target_name}\n"
          f"    LEARNMATE_RETRIEVAL_STRATEGY=rrf\n"
          "and, so documents uploaded afterwards land in the same layout:\n"
          "    LEARNMATE_QDRANT_SCHEMA=v2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
