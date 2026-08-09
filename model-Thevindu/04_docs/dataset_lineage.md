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
| Local real-corpus outputs | Under gitignored `processed/` | Not in git |

## Live pointer (application-facing)

```yaml
live_model_version: null   # set after promotion checklist
fallback_model: gemini-2.0-flash
```

Dinura's `components-Dinura` already supports swapping the generator via `LEARNMATE_GENERATOR_BACKEND=http`.
