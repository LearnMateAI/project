# EXP-001 — Dataset pipeline smoke test (synthetic corpus)

| Field | Value |
|-------|-------|
| Date (UTC) | 2026-08-06T15:36:41Z |
| Operator | model-Thevindu track |
| Dataset version | `lm-legal-smoke-v1` |
| Goal | Prove Stages 1–3 run end-to-end before any real statute PDFs exist |
| Command | `python scripts/run_pipeline.py --create-samples --mock --dataset-version lm-legal-smoke-v1` |
| Stage 2 mode | **mock** (no LLM API calls, $0) |

## Inputs

- 6 synthetic PDFs in `data/sample_pdfs/` (Penal Code, Constitution FR, Evidence, Civil Procedure, Companies, SC judgment)
- Manifest: `manifests/sample_manifest.csv`
- Config: `config/pipeline_config.yaml` (defaults)

These PDFs are **not** real law. They mimic Cap./CHAPTER/PART/`N.` section layout so structure detection and semantic chunking can be tested.

## Results

### Stage 1 — Parse & chunk

| Metric | Value |
|--------|-------|
| Documents processed | 6/6 ok (0 hard failures) |
| Chunks emitted | 33 |
| Header/footer lines stripped | 2–3 per document |
| Per-doc reports | `reports/parse_SAMPLE-00{1–6}.json` |

Observations:
- Section/chapter boundaries were detected; chunks are section-scoped, not fixed windows.
- Several short title/heading fragments flagged `below min_chunk_chars` (`ok_with_warnings`) — failures are visible, not silent.
- Output: `data/intermediate/stage1_chunks.jsonl`

### Stage 2 — Instruction pairs

| Metric | Value |
|--------|-------|
| Mode | mock |
| Pairs out | 99 (33 chunks × 3 types × 1) |
| Errors | 0 |
| Traceability | every pair has `chunk_id` + `doc_id` |

Output: `data/intermediate/stage2_pairs.jsonl`

### Stage 3 — Document-level split

| Split | Pairs | Documents |
|-------|-------|-----------|
| train | 69 | SAMPLE-001, 002, 003, 006 |
| val | 15 | SAMPLE-004 |
| test | 15 | SAMPLE-005 |

Assignment (seed=42): see `data/output/split_assignment.json`.

**Subject-balance warnings (expected with 6 docs / 6 subjects):** val and test each hold one document, so most subjects are absent from those splits. The pipeline correctly emitted warnings rather than silently claiming balance. With the real 25-document target corpus this warning surface is the gate before production training.

Outputs: `data/output/{train,val,test}.jsonl`

## Verdict

**PASS** — pipeline is structurally working. Ready for Part 2 (fine-tuning notebook) against `lm-legal-smoke-v1` artifacts. Real-corpus run still pending PDF download from `manifests/target_corpus_manifest.csv` + `--live` Stage 2.

## Not claimed by this experiment

- No real statute was parsed
- No live LLM pair generation
- No model training
- Subject coverage across val/test is intentionally incomplete at this scale
