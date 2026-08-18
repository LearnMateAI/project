# lm-legal-v0.1 processed snapshot

Tracked on **`thevindu-dev`** so teammates can inspect the real dataset without rerunning Stage 1–3.

| File | What it is |
|------|------------|
| `cleaned_text/` | 19 parsed documents |
| `chunks.jsonl` | 1,280 chunks |
| `pairs.jsonl` | 2,534 kept instruction pairs (GI-001 validator on) |
| `train.jsonl` / `val.jsonl` / `test.jsonl` | Chapter-group split |
| `test_strict.jsonl` | Whole-document holdout (4 subjects) |
| `subject_balance_report.json` | Per-subject counts |
| `pairs.summary.json` | 26 rejects (1.0%) |

Do not train a new run by silently mixing these with a later corpus. New work is `lm-legal-v0.2` in a new `processed_v02/` directory.
