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

## Not a backdoor

`legal-1.5b` is `experimental: true` and `selectable_default: false`. Default remains
`LEARNMATE_GENERATOR_MODEL` (Qwen 2.5 3B). Failed-gate adapters stay out of the silent default.

## Flags

- `LEARNMATE_HYBRID_BM25=0` restores ANN-only retrieve.
- Omit `model_id` / `summary_style` / `difficulty` → previous behaviour.

## Before merging to main

1. BM25: inspect `retrieval_mix.rerank_kept` on chat turns — if BM25-only chunks are never kept, report that rather than assuming hybrid helped.
2. Any newly selectable default: run `acceptance_thresholds.yaml` the same way as the ML track.
