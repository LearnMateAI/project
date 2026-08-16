# 01 — Dataset Pipeline

Three-stage offline pipeline that turns a folder of Sri Lankan legal PDFs into a fine-tuning-ready instruction dataset for LearnMateAI.

```
PDF folder + manifest CSV
        │
        ▼
 Stage 1  parse → clean headers/footers → detect Cap/Chapter/Section → semantic chunks
        │         (+ per-document parse report)
        ▼
 Stage 2  chunks → Q&A / summary / MCQ instruction pairs (chunk_id-traceable)
        │
        ▼
 Stage 3  whole-document train/val/test split + subject-balance warnings
        │
        ▼
 data/output/{train,val,test}.jsonl
```

## Quick start (smoke test — already proven)

```bash
cd model-Thevindu/01_dataset_pipeline
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
python scripts/run_pipeline.py --create-samples --mock --dataset-version lm-legal-smoke-v1
```

This regenerates six synthetic but structurally realistic PDFs, runs all three stages in **mock** mode (no LLM API spend), and writes:

| Output | Path |
|--------|------|
| Chunks | `data/intermediate/stage1_chunks.jsonl` |
| Pairs | `data/intermediate/stage2_pairs.jsonl` |
| Splits | `data/output/train.jsonl`, `val.jsonl`, `test.jsonl` |
| Parse reports | `reports/parse_SAMPLE-*.json` |
| Summaries | `reports/stage{1,2,3}_summary.json`, `subject_balance_report.json` |
| Experiment log | `experiments/EXP-001_smoke_test.md` |

## Manifests

- **`manifests/target_corpus_manifest.csv`** — target set of **25 real** Sri Lankan legal sources (statutes, codes, case law, official portals) across the platform subject areas. Every `source_url` was checked against CommonLII, Parliament, documents.gov.lk, Supreme Court, SriLankaLaw.lk, LankaLaw, or consumeraffairs.gov.lk listings. Status column is `verified_listing` (URL confirmed to resolve to that source); you still need to download PDFs into `data/raw_pdfs/` and add a `filename` column (or join table) before Stage 1 on the real corpus.
- **`manifests/sample_manifest.csv`** — six synthetic docs used for the smoke test.

Subject area vocabulary: `config/subject_areas.yaml`.

## Stage details

### Stage 1 — `scripts/stage1_parse_chunk.py`
- Extracts text with `pdfplumber`
- Strips headers/footers/page numbers via configurable regexes
- Detects `CHAPTER` / `PART` / `N.` section boundaries
- Chunks on those boundaries (oversized sections split on paragraph breaks; orphans merge) — **not** fixed-size windows
- Tags each chunk with `subject_area` from the manifest
- Writes a **per-document** report (`reports/parse_<doc_id>.json`) so failures are visible

### Stage 2 — `scripts/stage2_generate_pairs.py`
- Emits Q&A, summary, and MCQ pairs per chunk
- Every pair carries `chunk_id` + `doc_id` for lineage
- `--mock` (default): deterministic template pairs, $0 cost
- `--live`: OpenAI-compatible API using `LM_API_KEY`, optional `LM_API_BASE`, `LM_MODEL`

### Stage 3 — `scripts/stage3_split_dataset.py`
- Assigns **entire documents** to train/val/test (default 70/15/15, seed 42)
- Stratified preference so subjects are not all dumped into train
- `reports/subject_balance_report.json` **warns** if any subject area is completely missing from val or test

## Real corpus (when ready)

1. Download PDFs listed in `target_corpus_manifest.csv` into `data/raw_pdfs/`
2. Create a run manifest with columns `doc_id,filename,title,subject_area,doc_type`
3. Run:

```bash
python scripts/run_pipeline.py --pdf-dir data/raw_pdfs --manifest manifests/your_run_manifest.csv --live --dataset-version lm-legal-v0.1
```

Budget note: prefer cheap models / Gemini Flash for Stage 2 drafting; keep `--mock` for CI and structural regression.

## Config

All knobs live in `config/pipeline_config.yaml`.
