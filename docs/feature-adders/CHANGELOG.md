# Feature adders — changelog

Logged on `thevindu-feature` (copied from `main`). Do not merge to `main` until the
Tier 3 items have a before/after eval note.

## Shipped on this branch

| Feature | Why | Seam |
|---------|-----|------|
| Summary `narrative` / `structured` | Keep connected prose as the default; add a second mode for list-like statutes instead of silently reversing the deck | `summary.py`, Gate 1/2, `GenerateRequest.summary_style` |
| MCQ `easy` / `medium` / `hard` | Medium is today's prompt unchanged; easy/hard are additive | `mcq.py`, item `difficulty`, Analytics |
| MCQ distractor check | Gate 2 judge check that wrong options are actually false; reuses `MAX_ATTEMPTS = 2`; hard tier slightly more lenient | `rubrics.py` |
| UI refresh | Empty states, queued vs running job copy, optional selectors, export buttons, mobile padding | frontend only |
| Export docx/pptx | Format stored judged content; no regenerate | `GET /api/resources/{id}/export` |
| BM25 hybrid retrieve | Additive: ANN top 20, BM25 top 10, merge, **existing** reranker. Logged as `ann` / `bm25` / `both` | ingest sidecar + `retrieve.py` |
| Multi-model | Registry + optional `model_id`; one llama.cpp generator at a time; unload/reload; experimental LoRA labelled, not default | `models_registry.yaml`, `GET /api/models` |
| Upload docx / pptx / tex | Same extract → clean → chunk → embed path as PDF, so MCQ/summary/chat work on lecture slides and LaTeX notes. `.doc`/`.ppt` rejected with a save-as hint. | `extract_office.py`, `validate_upload`, DocumentsCard |

## Latency, quality, failures (this pass)

Full analysis: [LATENCY_QUALITY_FAILURES.md](LATENCY_QUALITY_FAILURES.md). Phase 2 code, still on this branch, no default-model change:

| Item | Why |
|------|-----|
| Stage timings on chat / passage-resource jobs | `rewrite_ms`, `retrieve_ms`, `generate_ms`, `judge_ms`, `model_load_ms` on the result (and `progress.timings`); INFO log per turn |
| Cached BM25Okapi per `doc_id` | Stop rebuilding on every retrieve; word-tokenise chunks; invalidate on ingest |
| `error_code` on failed jobs | `storage` / `model` / `parse` / `timeout` / `interrupted` / `unknown`; frontend `errorMessage` branches |
| `LEARNMATE_JOB_TIMEOUT_S` | Default 0 (off). When set, fail between graph nodes — does not abort llama.cpp mid-token |
| Resource persist of best-scoring attempt | Same policy as chat; full attempt trail kept |

## Not a backdoor

`legal-1.5b` is `experimental: true` and `selectable_default: false`. Default remains
`LEARNMATE_GENERATOR_MODEL` (Qwen 2.5 3B). Failed-gate adapters stay out of the silent default.

## Flags

- `LEARNMATE_HYBRID_BM25=0` restores ANN-only retrieve.
- `LEARNMATE_JOB_TIMEOUT_S=0` leaves jobs unbounded (whole-document runs).
- Omit `model_id` / `summary_style` / `difficulty` → previous behaviour.

## Before merging to main

1. BM25: inspect `retrieval_mix.rerank_kept` on chat turns — if BM25-only chunks are never kept, report that rather than assuming hybrid helped. **2026-09-04 (`thevindu-models`):** on `Company-law-part1-notes.pdf` (10 questions, in-process hybrid retrieve) BM25-only **was** kept in top-3 once (L-6: ann 3 / bm25 1 / both 26). Leave `LEARNMATE_HYBRID_BM25=1`.
2. Any newly selectable default: run `acceptance_thresholds.yaml` the same way as the ML track. **2026-09-04:** no `selectable_default` was flipped. Qwen generator 1.00/1.00; Phi and Gemma rejected; Llama and Granite judges 5/5 (Granite candidate only). E5 and L-12 lost their toy-fixture “next trial” status on the real PDF. Four-eyes review of `thevindu-models/RESULTS.md` has not happened.

