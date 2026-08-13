# Dataset lineage

```
official free legal PDF / HTML
        │
        ▼
01 Stage 1 chunks  (chunk_id, doc_id, subject_area)
        │
        ▼
01 Stage 2 pairs   (pair_id → chunk_id)
        │
        ▼
01 Stage 3 splits  dataset_version
        │
        ▼
02 LoRA run        run_id / model candidate
        │
        ▼
03 eval registry   passed? → promote live pointer
```

## Dataset versions

| dataset_version | notes | status |
|-----------------|-------|--------|
| `lm-legal-smoke-v1` | Synthetic sample PDFs | Smoke only (see EXP-001) |
| `lm-legal-smoke-v2` | Synthetic sample PDFs; first live `gpt-4o-mini` pair generation (33 chunks → 66 pairs → 46/10/10) | Smoke only — pipeline proof, not a training candidate |
| `lm-legal-v0.1` | **First build from the real corpus.** 21 real documents → 19 parsed → 1,280 chunks | In progress — Stage 2 |
| Local outputs | Under gitignored `processed*/` | Not in git |

> **Both smoke versions were built from the same six synthetic one-page PDFs** in
> `data/sample_pdfs/`, whose cleaned text is headed `(SYNTHETIC EXCERPT)`. The only
> difference between v1 and v2 is mock vs live pair generation. Neither has ever seen
> the real corpus in `data/raw_pdfs/`. `lm-legal-v0.1` is the first version that has.

## Known issue GI-001 — ungrounded section citations at Stage 2

**Found:** 2026-08-13, during the mandatory `--limit 20` review before the full
`lm-legal-v0.1` generation run. Caught exactly where that checkpoint is meant to catch
things — on 40 sample pairs, not on a full-corpus batch.

**Measurement:** 15 of 40 pairs (**38%**) asserted a section, article or chapter number
that does not appear in their excerpt. Concentrated in `summary` pairs (12 of 15).

**Why it mattered:** `acceptance_thresholds.yaml` gates on groundedness ≥ 0.85 and
hallucination ≤ 0.15. Training on pairs that invent citations teaches the model the exact
behaviour the gate rejects. Stage 2 had **no automated validation**, so nothing would have
flagged this before evaluation.

**Root causes, both confirmed against the data:**

1. *Chunks starting mid-provision.* 320 of 1,332 chunks (24%) carried no `section_id`,
   because a continuation chunk doesn't restate its number and `section_heading` degraded
   to the enclosing `PART II`. The generator filled the gap from pretrained knowledge —
   one excerpt reading `Previous or subsequent conduct. (2) The conduct of any party...`
   produced *"Section 2 states that..."*, mistaking a subsection marker for a section.
2. *Table-of-contents fragments treated as substantive text.* A TOC chunk listing
   `JUDICIAL SERVICE COMMISSION 111D ... 111E ...` produced a detailed answer about the
   *Audit Service Commission* under 153C/153D — a topic absent from the excerpt entirely.

**Fixes applied:**

| # | Fix | Where |
|---|-----|-------|
| 1 | Drop TOC/index chunks (dotted leaders, or short lines ending in page numbers) | `preprocess_dataset.py: looks_like_toc()` |
| 2 | Forward-fill the parent section onto continuation chunks, flagged `section_inherited` | `preprocess_dataset.py: process_one()` |
| 3 | Tell the generator which provision it is reading, or that the number is unknown and must not be stated | `generate_training_pairs.py: live_pair()` |
| 4 | State the citation rule in every prompt; stop telling the summary prompt to "preserve section numbers" | `scripts/stage2_generate_pairs.py: PAIR_PROMPTS` |
| 5 | Reject offending pairs during generation, fail-closed | `validate_pairs.py` wired into Stage 2 |

**Re-validated** on the same 20-chunk / 40-pair sample after the fixes:

| Metric | Before | After |
|--------|--------|-------|
| Ungrounded citations (hand review) | 38% | — |
| Ungrounded citations (validator) | 15% | **0%** |
| Chunks with no `section_id` | 320 / 1,332 (24%) | 153 / 1,280 (12%) |
| TOC chunks reaching Stage 2 | 52 | 0 |
| Median answer length | 759 chars | 653 chars |
| Answers declined / evasive | 0 | 0 |

Answers stayed substantive; 15 of 40 now correctly say "this provision" where the number
isn't visible, instead of inventing one.

**Regression guard:** `test_validate_pairs.py` pins six hand-classified cases, including
three that must *pass* (a legitimately inherited `153A`, a marginal-note `5.`, and
line-initial `147/148/149`) so the validator can't drift into over-rejecting. The TOC case
is deliberately expected to pass the validator — its citations really are in the excerpt —
and is caught upstream by fix 1 instead.

## Source tiering and Tier B disclosure

Every row in `manifests/target_corpus_manifest.csv` carries a `source_tier`:

| Tier | Meaning | Examples |
|------|---------|----------|
| A | Official government or judiciary publisher | `parliament.lk`, `documents.gov.lk`, `supremecourt.lk`, `nipo.gov.lk` |
| B | Unaudited secondary source (LII or commercial aggregator) | `commonlii.org`, `lankalaw.net`, `srilankalaw.lk` |

Current target corpus: **13 Tier A / 19 Tier B documents.** Any dataset version built from
this manifest inherits Tier B sources in the following subject areas, and this must be
disclosed in the model card for any model trained on it:

| Subject area | Tier B dependency | Why no Tier A source |
|--------------|-------------------|----------------------|
| `criminal_procedure` | Bail Act No. 30 of 1997 | `documents.gov.lk` lists Act 30/1997 but its English and Tamil downloads are disabled — Sinhala only |
| `civil_procedure` | Judicature Act No. 2 of 1978 | No `documents.gov.lk` acts index exists for 1978 (404) |
| `property_land` | Prevention of Frauds Ordinance | 1840 Ordinance — predates the official online archive entirely |
| `criminal_law` | Poisons Opium and Dangerous Drugs Ordinance | 1929 Ordinance — predates the official online archive entirely |
| `labour_industrial` | Shop and Office Employees Act | No `documents.gov.lk` acts index exists for 1954 (404) |

Two risks follow from Tier B use, and neither is caught by the evaluation gate:

1. **Licensing.** `lankalaw.net` and `srilankalaw.lk` are commercial legal-research products.
   The underlying law is public domain, but a publisher's consolidation and its terms of use
   are not automatically usable for building or redistributing a derived training set.
   Their terms must be checked per site before a dataset built on them is published.
2. **Transcription accuracy.** A secondary consolidation can lag amendments or carry
   transcription drift. A groundedness check only confirms an answer matches its supplied
   source — it cannot detect that the source itself is wrong. Before trusting any model
   version built on Tier B text, spot-check at least one section per Tier B document against
   an independently verifiable reference.

This is a documented, deliberate call affecting five identified subject areas. It should be
raised with the project mentor rather than settled inside the team.

## Live pointer (application-facing)

```yaml
live_model_version: null   # set after promotion checklist
fallback_model: gemini-2.0-flash
```

Dinura's `components-Dinura` already supports swapping the generator via `LEARNMATE_GENERATOR_BACKEND=http`.
