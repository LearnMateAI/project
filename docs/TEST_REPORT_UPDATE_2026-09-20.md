# Test Report Update — 2026-09-20

What changed in `docs/TEST_REPORT.md` between **Version 2.0** (2026-09-18) and
**Version 2.1** (2026-09-20). This file is the diff, not a replacement — the full
report is still [docs/TEST_REPORT.md](TEST_REPORT.md); this is here so a reviewer can
see just the new material without re-reading the whole thing.

---

## Summary of changes

1. **New §8, "Model comparison — `thevindu-models`"** (8 subsections) — the substantive
   addition. Full text below.
2. Version bumped 2.0 → 2.1, and a short pointer note added under the report title.
3. Mission (§1) gained a 4th objective describing this update's verification work.
4. Target test items (§2) gained a row for `thevindu-models/`.
5. Branch survey (§7) — the `thevindu-models` row now points at the new §8 for detail.
6. **Renumbering**: "Known gaps" moved §8 → §9; "References" moved §9 → §10. All
   in-document cross-references (§8 mentions in §1, §2, §3.3) were updated to match.
7. Known gaps (§9) gained a 7th item about the comparison work's own open review.
8. References (§10) gained an entry for `thevindu-models`'s source files.

Nothing in §1–§7 or §9–§10's substance changed — only section numbers and a handful of
cross-reference pointers, plus the two additions in items 3, 4, 7, and 8 above (each
quoted in full below, alongside the new §8).

---

## New: intro pointer (under the title)

> **2026-09-20 addition:** §8 adds the `thevindu-models` branch's laptop model-comparison
> work — three live roles (generator, judge, embeddings), each benchmarked against two
> off-the-shelf alternatives, with the resulting keep/promote decisions and why. Every
> number quoted there was independently re-read from that branch's raw result files for
> this report, not copied from its summary on faith.

## New: §1 mission, 4th objective

> 4. **Verify, not transcribe, the model-selection work on `thevindu-models`** (§8) — the
>    branch already ran its own comparisons; this pass's job was to check its safety test
>    still passes and that its headline numbers match its own raw result files before
>    repeating them here.

## New: §2 target test items, new row

| Area | What it is | In scope this pass |
|---|---|---|
| `thevindu-models/` (local branch) | Laptop drop-in comparisons for generator/judge/embeddings/reranker | Reviewed in depth (§8) — its own safety test re-run and its raw results independently checked; not merged, not part of the 177-test combined total |

## New: §9 known gaps, 7th item

> 7. **`thevindu-models`'s comparisons have no four-eyes review and no end-to-end chat
>    p95** (§8.7–8.8). Granite-as-judge is a documented candidate, not a validated one; the
>    branch is also 38 commits behind `main` and would need a rebase before it could be
>    reviewed against current code.

## New: §10 references, new entry

> - `thevindu-models/README.md`, `RESEARCH.md`, `RESULTS.md`, `comparison_registry.yaml`,
>   `results/gguf.json`, `results/real_pdf.json`, `results/retrieval.json`,
>   `integrated-backend/tests/test_comparison_registry.py` — branch `thevindu-models`,
>   detailed in §8

---

## New: full §8 — Model comparison — `thevindu-models` (choosing the best drop-in per role)

`thevindu-models` is a separate, unmerged local branch (branched from `thevindu-feature`)
that asks a narrower question than the LoRA track in `model-Thevindu/` (§3.1). That track
asks "can we train a better model" — and its one candidate failed the gate. This branch
asks instead: *for each of the live app's model-shaped roles, is there a better
**off-the-shelf, laptop-sized drop-in** than what's already running, without training
anything?*

**Verified for this report**, not transcribed from the branch's own summary: a git
worktree of `thevindu-models` was checked out separately, its safety test
(`integrated-backend/tests/test_comparison_registry.py`) was re-run and passes **3/3** —
Qwen 2.5 3B stays the sole `selectable_default`, every comparison candidate stays
`experimental: true`, and the comparison YAML's candidate counts and embedding
query/passage prefixes are exactly what the eval scripts assume. Every headline number
below was independently re-read from the branch's own raw result files
(`results/gguf.json`, `results/real_pdf.json`, `results/retrieval.json`) and matches its
`RESULTS.md` tables exactly.

### 8.1 Methodology

| | |
|---|---|
| Machine | One Windows laptop, CPU-only (AMD64, Intel Family 6 Model 186) — **not** Colab T4, **not** a uvicorn server p95 |
| Toy fixture | `fixtures/legal_retrieval.jsonl` — 36 chunks, 14 queries |
| Real fixture | `integrated-backend/data/Company-law-part1-notes.pdf` — 7 pages → 34 live-ingested chunks, 10 questions |
| Generator/judge fixtures | `fixtures/generator_prompts.jsonl`, `fixtures/judge_gold.jsonl` |
| Promotion rule | A candidate must beat the live baseline on **every** primary metric for its role, not just one — `RESEARCH.md`'s "What 'better' means" table |
| Safety rule | No candidate may carry `selectable_default: true` while `experimental: true` (same rule as the LoRA track, §3.1) — enforced by the registry parser itself, confirmed by the re-run test above |

Three model roles were compared, each against the live baseline plus two alternative
candidates from a *different* model family (never "another Qwen," so a win means an
architecture win, not a size change).

### 8.2 Generators — vs Qwen 2.5 3B Instruct (live)

| Candidate | Grounded hit rate | JSON validity | Mean ms | Verdict |
|---|---:|---:|---:|---|
| **Qwen 2.5 3B (live)** | **1.00** | **1.00** | 15,082 | baseline — kept |
| Gemma 2 2B Instruct | 0.67 | 0.00 | 14,857 | reject — fails JSON validity |
| Phi-3.5 Mini Instruct | 0.00 | 0.00 | 17,822 | reject — fails both metrics |

**Why Qwen stays:** it is the only candidate that both stayed grounded in the source
passage *and* produced schema-valid MCQ JSON on this laptop. Gemma matched Qwen's speed,
but its MCQ item failed the live "4 options, `answer` ∈ `options`" check. Phi's run
completed (not an out-of-memory skip) but decoded to garbage bytes under the app's empty
`chat_format` contract — a genuine drop-in failure, not a missing file.

### 8.3 Judges — vs Llama 3.2 3B Instruct (live)

| Candidate | Gold-label agreement | Mean ms | Verdict |
|---|---:|---:|---|
| **Llama 3.2 3B (live)** | **1.00 (5/5)** | 32,967 | baseline — kept |
| Granite 3.2 2B Instruct | 1.00 (5/5) | 36,879 | matches agreement, ~12% slower — **promotable candidate**, not promoted |
| Gemma 2 2B (judge role) | 1.00 (5/5) | 38,323 | not a drop-in — only agrees after folding the system prompt into the user turn, which the live judge node does not do |

**Why Llama stays, and why Granite is worth watching:** Granite ties Llama on the
gold-label pass/fail set without a large latency regression — under the branch's own
rule ("match or beat agreement without a large latency cost"), that clears the bar to be
a *candidate*. It has not been promoted: the branch's own four-eyes review checklist is
still unchecked, and a judge swap changes what "passed" means for every future
generation — that stays a documented option, not a flipped default, until a second
person signs off.

### 8.4 Embeddings — vs all-MiniLM-L6-v2 (live)

The most important finding in this track is that the toy fixture and a real document
**disagree**, and the branch trusted the real one over the synthetic win:

| Candidate | Toy NDCG@5 | Toy query ms | Real-PDF NDCG@5 | Real-PDF gold-in-top-3 | Real-PDF query ms |
|---|---:|---:|---:|---:|---:|
| **MiniLM-L6 (live)** | 0.9209 | 37.7 | **0.9500** | **1.00** | **33.7** |
| BGE-small-en-v1.5 | 0.9116 | 72.9 | 0.9377 | 1.00 | 63.4 |
| E5-small-v2 | **0.9379** | 196.6 | 0.9133 | 0.90 | 61.4 |

**Why MiniLM stays, despite E5 "winning" first:** on the 36-chunk toy fixture, E5's
asymmetric query/passage training gave it the best NDCG. Re-run against a real 7-page
company-law PDF, that reversed — MiniLM beat E5, and E5 missed the gold chunk in its top
3 on one question entirely. The toy fixture's ~5× query-latency gap also shrank to ~1.8×
on the real document. A model that wins on 14 synthetic queries and loses on a real one
is exactly the case a promotion gate exists to catch. Switching embedders also forces a
mandatory re-ingest of every stored PDF (vectors from different models are not
comparable) — not a decision to make from one fixture.

### 8.5 Reranker and retrieval agent (a related fourth comparison)

Run alongside the embeddings work, since both sit in the retrieve stage:

| Reranker | Toy NDCG@5 | Real-PDF NDCG@5 | Real-PDF ms/~20 pairs | Verdict |
|---|---:|---:|---:|---|
| **MiniLM-L-6 (live)** | 0.9473 | 0.992 | 1,069 | baseline — kept |
| MiniLM-L-12 | 0.9736 | 0.992 (tie) | 2,128 (2×) | reject — no real-document lift, 2× cost |
| BGE-reranker-base | 0.9473 (tie) | not re-run | 7,047 | reject — ties L-6 at ~11× the latency on the toy fixture alone |

Retrieval agent (ANN-only vs. the live hybrid ANN+BM25): tied on both fixtures, but on
the real PDF, BM25-only chunks **did** survive into the reranked top-3 once across ten
questions (26 of the kept chunks were found by both methods, 1 was BM25-only). **Hybrid
stays on** — a tie is not evidence it is a no-op, and the one case where BM25 alone
surfaced the answer is exactly what the flag exists for.

### 8.6 Decision summary

None of the eight candidates evaluated changed a live default. `.env` and
`models_registry.yaml`'s `selectable_default` were not touched — confirmed by the
registry-safety test in the intro to this section, not just asserted:

| Role | Live default | Promote now? | Why |
|---|---|---|---|
| Generator | Qwen 2.5 3B | No | No alternative beat Qwen on both grounding and JSON validity |
| Judge | Llama 3.2 3B | No | Granite is a viable candidate, but four-eyes review hasn't happened |
| Embeddings | all-MiniLM-L6-v2 | No | The toy-fixture winner (E5) lost on the real document |
| Reranker | MiniLM-L-6 | No | Larger/alternate rerankers didn't lift real-document quality |
| Retrieval agent | Hybrid ANN+BM25 | Keep as-is | Already the live default; real-PDF evidence supports keeping it on |

### 8.7 What this track does not claim

Directly from the branch's own "What we are not claiming" section, because it is the
right level of honesty for this report too: Colab T4 numbers from the LoRA eval are not
this laptop's GGUF numbers; this laptop's retrieve latency is not a uvicorn chat p95; a
36-chunk fixture does not mean retrieval is "solved"; and end-to-end chat p95 with any of
these candidates has not been measured (`end_to_end_chat_p95_ms: null` in
`results/real_pdf.json` — the live stack was down when this was run, the same constraint
as §3.4/§3.6 in this report).

### 8.8 Status

Not merged to `main`. Per the branch's own next-actions list, a second person needs to
sign off on `RESULTS.md` before anything here becomes a registry default, and the branch
predates `main`'s multi-format ingestion work — it is 38 commits behind (§7) — so it
would need a rebase before that review could even happen against current code.
