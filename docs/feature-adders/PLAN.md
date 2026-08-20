# Feature adders — plan, feasibility, and ship rules

**Branch:** `thevindu-feature` (copied from `main`). Do not merge to `main` until each item’s gate below is signed.  
**Pattern:** slot into existing seams (task prompts, Gate 1/2, `GenerateRequest`, retrieve node, `.env`). No new architecture.

---

## Decision already taken (do not reverse silently)

Summaries stay **narrative connected prose by default**. “Bolder / point-by-point” is a **second mode** (`structured`), not a replacement. That is option (b) from the spec: students can override; a list-like statute can default to structured via a heuristic.

MCQ **medium** = today’s generator, unchanged. Easy and hard are additive.

---

## Feasibility

| # | Feature | Feasible? | Seam | Risk | Re-eval before `main`? |
|---|---------|-----------|------|------|------------------------|
| 1 | Summary `narrative` / `structured` | **Yes** | `summary.py` prompt + Gate 1 length/points + Gate 2 rubric line | Low | Light spot-check |
| 2 | MCQ `easy` / `medium` / `hard` | **Yes** | `mcq.py` prompt + stamp `difficulty` on items + params | Low | Light spot-check |
| 3 | UI/UX refresh | **Yes** | empty states, JobProgress copy, optional selectors, mobile | Low | No |
| 4 | MCQ distractor checker | **Yes** | Gate **2** extra rubric (not a new retry budget) | Moderate — false rejects | Yes — watch reject rate |
| 5 | Export docx/pptx | **Yes** | `GET /api/resources/{id}/export` reads stored content only | Moderate (new deps) | No |
| 6 | BM25 hybrid | **Yes** | ingest sidecar + retrieve merge **before** existing reranker | High — live answers | Yes — ANN vs BM25 vs both |
| 7 | Multi-model | **Yes** | registry YAML + optional `model_id`; **one** llama.cpp load; unload/reload | High — live generation | Yes — per-model gate; experimental LoRA stays labelled |

**Not feasible / not done:** keeping two GGUFs in RAM for concurrent roles is already how generator+judge work (two files). Keeping **two generators** loaded at once is **rejected** — same mutable-context rule as the single worker.

**Promotion backdoor:** a failed LoRA may appear as `experimental: true` in the registry. It must **not** become `selectable_default`. Default remains the live Qwen 2.5-3B GGUF.

---

## Suggested git layout (this branch)

Work lands on `thevindu-feature` in **tier order**, one commit family per feature. Optional pointers (created if isolation is needed later):

- `feature/summary-style`
- `feature/mcq-difficulty`
- `feature/ui-refresh`
- `feature/mcq-distractor-checker`
- `feature/export-office`
- `feature/bm25-hybrid`
- `feature/multi-model`

Tier 1 can merge internally as soon as spot-checked. Tier 3 stays on this branch until eval notes exist.

---

## Env / flags (live path safety)

| Flag | Default | Meaning |
|------|---------|---------|
| `LEARNMATE_HYBRID_BM25` | `1` on this branch | Hybrid retrieve; set `0` to restore ANN-only |
| `LEARNMATE_GENERATOR_MODEL` | unchanged | Fallback when `model_id` omitted |
| Registry file | `learnmate/models_registry.yaml` | Selectable generators |

---

## Acceptance (Tier 3)

Before merging BM25 or a new default model to `main`:

1. BM25: log `retrieval_mix` (`ann` / `bm25` / `both`) and report how often the reranker keeps BM25-only chunks.
2. Models: run the same `acceptance_thresholds.yaml` discipline as the ML track; experimental ids stay experimental.

---

## Demo order

1. Generate a **narrative** summary (looks as today).  
2. Toggle **structured** on a numbered-section statute.  
3. Generate **easy** vs **hard** MCQs; difficulty badge on the quiz.  
4. Empty Documents/Resources/Chat states.  
5. Export a resource to Word.  
6. (If enabled) job message “Loading generator …” on model switch; analytics filter by model.
