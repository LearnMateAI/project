# Screencast script (≤ 2 min 30 s)

ACL/EMNLP System Demonstrations require a screencast of at most 2.5 minutes with narration.
Record at 1920×1080. Before recording, bring the stack up with the classroom features on
(see "Setup" below) and replay the simulated class so the heatmap has data.

| Time | Screen | Narration (read at a normal pace) |
|---|---|---|
| 0:00–0:15 | Title slide: LearnMate logo, one-line claim, "all models local" | "LearnMate is a study assistant that runs entirely on local models. This demo shows what changes when a whole class uses it with the same course notes." |
| 0:15–0:35 | Library → upload *Contract Law* chapter → Ready in seconds (already ingested) | "Documents are stored by content hash, so when a second student uploads the same notes, nothing is re-processed and every student talks to the same document." |
| 0:35–1:00 | Workspace, "Ask the record": *What makes a contract enforceable?* Answer streams with page chips; open "Show the text it used" | "A question is answered from the notes. Retrieval fuses dense vectors with a BM25 index that lives inside the vector database, and a reranker picks the passages. The answer cites its pages, and a second model judges it." |
| 1:00–1:20 | Second browser (Student B), same chapter: *What do you need for a contract to be legally binding?* Answer appears instantly with the green "Verified answer reused" badge; hover the badge | "Another student asks the same question in different words. The answer is reused instantly, but only because a duplicate-question model confirmed the two questions ask the same thing." |
| 1:20–1:30 | Student B asks *When is a contract NOT enforceable even with an agreement?* → normal generation, no badge | "A question about the exception looks almost identical as an embedding. The verifier rejects the match, so it gets a fresh answer." |
| 1:30–1:55 | "Class insights" tab: heatmap; hover a dark page; topics with badges; click a page → reader jumps to it | "Across the class, questions are clustered into topics and mapped onto pages. Dark pages are where students ask most and the answers land worst. Pages with fewer than three students stay hidden." |
| 1:55–2:15 | Terminal split: two `worker_main` processes draining the queue; `Ctrl+C`/kill one mid-answer; the other picks the job up after the lease lapses; `/api/health` jobs block | "Chat turns are jobs in MongoDB, claimed under renewable leases by a pool of workers that feed continuously batched model servers. Kill a worker and its job simply comes back." |
| 2:15–2:30 | Results table from the paper + repository URL | "Every number in the paper comes from a script in the repository. Code and the evaluation harness are open source." |

## Setup for recording

```
# integrated-backend/, venv active, databases up
python scripts/reindex_qdrant.py                    # once: v2 collection, prints .env lines
# .env: LEARNMATE_RETRIEVAL_STRATEGY=rrf, LEARNMATE_QDRANT_COLLECTION=..._v2,
#       LEARNMATE_QDRANT_SCHEMA=v2, LEARNMATE_CACHE_ENABLED=1
# For the worker segment additionally: models served (scripts/serve/llama_servers.sh),
#       LEARNMATE_*_BACKEND=http, JOB_QUEUE_BACKEND=mongo, JOB_RUN_IN_API=0
uvicorn server:app --port 8010
python -m app.jobs.worker_main --workers 2 --name worker-a      # terminal 2
python -m app.jobs.worker_main --workers 2 --name worker-b      # terminal 3
```

Record with two browser profiles (Student A, Student B) so the two accounts are visibly
different people.
