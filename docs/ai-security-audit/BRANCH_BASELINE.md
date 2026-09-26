# Branch baseline (read before judging the audit)

Fetched `origin` on 2026-09-26. Audit branch created from **`origin/main`**.

| Ref | Tip | Date | Relation to `main` |
| --- | --- | --- | --- |
| `origin/main` | `156b640` Merge PR #24 `thevindu-feature` | 2026-09-04 | Audit baseline |
| `origin/thevindu-feature` | 6 commits not in `main`; `main` has 37 not in this tip | — | Continues after the merge |
| `origin/deployment` | `9dccafc` merge into `tharumini-dev` | 2026-09-13 | **35 commits ahead of `main`** — this is the deployed-looking line |
| `origin/dinura-deployment` | `862812b` | 2026-08-31 | Older deploy trigger |
| `origin/dinura-final` | `7d1491a` | 2026-09-20 | 2 commits ahead of `main` (screenshots / convert / UI) |
| `origin/demo1` | `a3310b3` classroom-scale + eval harness | 2026-09-21 | Research/demo fork; **not** what `main` ships |

## What `origin/deployment` changes vs `main` (AI-relevant)

The engine on `deployment` is the same LangGraph chat + resource + MiniLM + Qdrant
stack. The delta is packaging and a few ingestion/UI files:

- `integrated-backend/Dockerfile`, `.dockerignore`, Keycloak theme tweaks
- `integrated-backend/app/config.py` (small)
- `integrated-backend/app/services/documents.py` (small)
- `integrated-backend/learnmate/ingestion/convert.py` (**added** — office/LaTeX path)
- Frontend restyle (Masthead, homepage, documents page); **no new LLM tools**
- **Removes** `docs/feature-adders/{PLAN,CHANGELOG,LATENCY_QUALITY_FAILURES}.md` from that tree

So findings about prompts, retrieval, the judge, and auth apply to **both** `main`
and the deployed line. Findings that mention `convert.py` / Docker are
deployment-ahead of `main`.

## What `origin/demo1` has that `main` / `deployment` do not

These exist only on `demo1` and are marked **Not present** in the audit of the
shipped product:

- `integrated-backend/learnmate/cache/answer_cache.py` and chat cache nodes
- `integrated-backend/eval/` (IR bench, latency, load test, metrics)
- `integrated-backend/learnmate/insights/` (classroom heatmap / confusion)
- Extra hybrid retrieval modules under `learnmate/retrieval/`

`main` already has hybrid ANN+BM25 (`HYBRID_BM25=True`), the MiniLM reranker,
query rewrite, and the two-gate evaluator. `demo1` adds **caching, a real eval
harness, and classroom analytics** on top.

## What this audit judged

The **live product** = `origin/main` engine + `origin/deployment` packaging.
`demo1` is cited only as “exists on a research branch; should be back-ported.”
