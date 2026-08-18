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
| `lm-legal-v0.1` | **First build from the real corpus.** 21 documents → 19 parsed → 1,280 chunks → 2,534 pairs → 1,590/339/325 + 280 strict | Built, trained, **eval FAIL** — do not promote |
| Local outputs | `processed_v01/` is **tracked on `thevindu-dev`** for evaluation. Smoke `processed/` and `processed_real/` stay gitignored. | See `FULL_WORKFLOW_AND_BRANCH_INVENTORY.md` |

### `lm-legal-v0.1` build record

Sources: 21 files in `data/raw_pdfs/`. `Black's-Law-4th-edition-1891.pdf` moved to
`data/excluded_from_corpus/` (an 1891 American dictionary, not Sri Lankan law, and at
11 MB it would have dominated the chunk count).

| Stage | Result |
|-------|--------|
| 1 — parse/clean/chunk | 19 of 21 OK, **1,280 chunks**; 52 TOC chunks dropped; every subject tagged from the manifest, none guessed |
| 1 — failures | Two scanned PDFs, no text layer. **Do not OCR** — text-layer replacements exist (see below). Not in `lm-legal-v0.1`; add in a later version |
| 2 — pair generation | live `gpt-4o-mini`, 2 per chunk → **2,534 kept, 26 rejected (1.0%)** by the GI-001 grounding gate, 0 API errors |
| 3 — split | `--group_by chapter --strict_holdout`, 189 units, seed 42 |

| Split | Pairs | Documents | Subjects |
|-------|------:|----------:|---------:|
| train | 1,590 | 15 | 11 |
| val | 339 | 14 | 11 |
| test | 325 | 13 | 11 |
| `test_strict` | 280 | 4 | 4 |

Verified: no strict-holdout document appears in train/val/test, no duplicate `pair_id`
across splits, no chunk in more than one split.

### Scanned-PDF replacements (not yet in the corpus)

Research on 2026-08-13 found text-layer sources for both Stage 1 FAIL files. OCR is not
needed. They were **not** downloaded into this dataset version — train `lm-legal-v0.1` as
it stands, then add these in a later version after a spot-read.

| Local file | What it actually is | Replacement | Caveats |
|------------|---------------------|-------------|---------|
| `Arbitration act 2.pdf` (35.5 MB scan) | Arbitration Act No. 11 of 1995 — identification confirmed | https://slnarbcentre.com/pdf/ARBITRATION-ACT.pdf (Tier B, 95 KB, 22 pages, extractable text, zero images) | OCR-derived text layer: typos such as `awad`/`award`, `shall like`/`shall lie`, `©` for `(c)`. Normalise before training |
| `Mediation Boards Act no 27.pdf` (20.6 MB scan) | **No Act No. 27 exists.** No. 27 of 1999 is the Judicature (Amendment) Act. Likely a 72→27 filename transposition for Mediation Boards Act No. 72 of 1988 (contents UNVERIFIED — local file has no text) | https://lankalaw.net/wp-content/uploads/2025/03/Mediation-Boards-Act-Consolidated-2024.pdf (Tier B, 294 KB, 17 pages, clean extractable text) | This is the **2024 consolidation** (amendments 15/1997, 21/2003, 4/2011, 9/2016, 2/2024), not the 1988 original. The official `mediation.gov.lk` 1988 PDF is Tier A but is itself a scan with zero extractable text |

Also corrected in the manifest from the file's own heading: `Mediation Boards Act no 21.pdf`
is **Mediation (Special Categories of Disputes) Act, No. 21 of 2003**, not "Mediation
Boards Act No. 21 of 1990". `subject_area` (`civil_procedure`) is unchanged; that file is
the `lm-legal-v0.1` strict holdout for civil procedure.

`documents.gov.lk` `/view/act/...` paths now 404 (site rebuilt as a JS app). Manifest
rows DOC-020, DOC-028, DOC-035, and the provenance URL on DOC-026 are marked stale.
DOC-026 itself is already downloaded and parsed.

### Two accuracy numbers, deliberately not interchangeable

Whole-document splitting was tried first and is **unusable on this corpus**. With 19
documents of very unequal size and most subjects holding one document, a subject must
land entirely in one split: `family_law` and `property_land` came out with **zero
training pairs**, eight subjects had no val or test, and val was 80% a single subject.

Grouping by `(document, chapter)` gives 189 units instead of 19 and puts every subject in
every split — at the cost of chapters of one statute appearing in both train and test.

| Metric | Split | Measures |
|--------|-------|----------|
| `in_corpus_accuracy (chapter-held-out)` | `test.jsonl` | Handling chapters of statutes partly seen in training |
| `accuracy (document-held-out)` | `test_strict.jsonl` | Generalisation to a statute never seen at any granularity |

The `accuracy ≥ 0.70` in `acceptance_thresholds.yaml` was written against the **second**
definition. A candidate can clear the first without clearing the bar the threshold
intended, so registry rows carry `eval_split` and `metric_definition` and the two must
never be compared as one number.

`test_strict.jsonl` reserves four whole documents, chosen as the smallest in each subject
that has two or more, so the cost in training data is minimal:

| Subject | Held-out document |
|---------|-------------------|
| civil_procedure | Mediation Boards Act No. 21 |
| constitutional_law | 21st Amendment |
| contract_law | Sale of Goods |
| criminal_procedure | Primary Courts' Procedure |

`family_law` is deliberately **skipped**: it has only two documents, and reserving one
left a single unit that could not cover train, val and test — the holdout would have
recreated the problem it exists to check. It therefore has no strict-generalisation
signal until a third family-law document is added.

Run both evaluations. If the two numbers land close together the leakage is doing little
work; if they diverge, that divergence is the finding, and it is worth having before
promotion rather than after.

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

## Known issue GI-002 — whole-document split left subjects with zero training pairs

**Found:** 2026-08-13, first Stage 3 run of `lm-legal-v0.1` after GI-001. Whole-document
assignment produced 61/31/8 ratios against a 70/15/15 target, `family_law` and
`property_land` with **zero training pairs**, eight subjects missing from val or test,
and val 80% a single subject.

**Why it happened:** the splitter assigns whole `doc_id`s. With 19 documents of very
unequal size (Criminal Procedure Code 312 chunks, Registration of Documents 16) and most
subjects holding one document, a subject must land entirely in one split. No seed or
manual document move can fix that.

**Fix:** group by `(doc_id, chapter/part)` — 189 units instead of 19 — and stratify per
subject. `--strict_holdout` reserves one whole document per multi-document subject as
`test_strict.jsonl`, unseen at any granularity. `family_law` is skipped because holding
out one of its two documents would leave a single unit that cannot cover train/val/test.

**Before / after (`lm-legal-v0.1`):**

| | Whole-document | Chapter-group + strict holdout |
|--|----------------|--------------------------------|
| Units | 19 | 189 |
| train / val / test | 1549 / 781 / 204 | 1590 / 339 / 325 |
| Subjects in all three splits | no | **yes, all 11** |
| Subjects with zero train pairs | family_law, property_land | none |
| True document-held-out set | none | 280 pairs / 4 documents |

**Metric names (not interchangeable):**

- `in_corpus_accuracy (chapter-held-out)` on `test.jsonl`
- `accuracy (document-held-out)` on `test_strict.jsonl`

The 0.70 bar in `acceptance_thresholds.yaml` was written against the second. Registry
rows carry `eval_split` and `metric_definition`.

**Subjects with no true generalisation test until another source document exists**
(corpus-coverage gap, not a splitter bug): `administrative_public`, `company_commercial`,
`criminal_law`, `evidence`, `intellectual_property`, `property_land`. `family_law` has two
documents but still no strict holdout for the reason above — needs a third.

Measured on the first real eval (`qwen25-lora-20260815-090709`): chapter-test accuracy
0.717 vs strict-test 0.836. They did **not** diverge in the direction leakage would
predict (strict was higher), so chapter leakage was not inflating the in-corpus number.

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
