# 02 — Fine-tuning (Qwen 2.5 + LoRA/PEFT)

Colab-ready notebook that fine-tunes **Qwen 2.5 Instruct** with **LoRA/PEFT only** (never full-weight fine-tuning) on Stage 3 `train.jsonl` / `val.jsonl`.

## Files

| Path | Role |
|------|------|
| `finetune_qwen25_lora.ipynb` | Training notebook |
| `sample_data/` | Copy of `lm-legal-smoke-v1` splits for dry-runs / path checks |
| `adapters/` | Saved LoRA adapters land here (`adapters/<run_id>/adapter/`) |
| `run_records/` | Mandatory run-record JSON per training run |
| `requirements.txt` | Local GPU reference deps (Colab installs inline) |

## How to run (Colab)

1. Upload this folder (or clone the repo) into Colab / Drive.
2. Runtime → GPU (T4).
3. Open `finetune_qwen25_lora.ipynb`.
4. Edit **only** the CONFIG cell (model size, paths, LoRA rank, epochs, LR, …).
5. Run all cells. The **final cell must write a run-record** next to the adapter — skip it and the candidate is invalid for evaluation.

## Config contract

Every hyperparameter that affects the run lives in the single `CONFIG` dict. The run-record serialises that dict plus:

- `dataset_version`
- `final_train_loss` / `final_eval_loss`
- `adapter_path`
- `completed_at_utc`

## Status

| Item | State |
|------|-------|
| Notebook structure / CONFIG / run-record cell | **Ready** |
| Smoke JSONL paths wired to Part 1 output | **Ready** |
| Full GPU training run on Colab | **Executed — 3 runs** (Colab T4, QLoRA 4-bit nf4) |

### Completed runs

| Run ID | Dataset | Steps | Wall clock | train / eval loss |
|--------|---------|-------|-----------|-------------------|
| `qwen25-lora-20260810-052502` | smoke | — | ~25 min | 1.7805 / 1.3199 |
| `qwen25-lora-20260813-054543` | smoke | — | ~10 steps | 1.5641 / 1.1592 |
| `qwen25-lora-20260815-090709` | `lm-legal-v0.1` | 597 | 93.7 min | **1.0377 / 1.2467** |

Base model for all three: `Qwen/Qwen2.5-1.5B-Instruct` (r=16, alpha=32, 7 target modules).
The last run's eval loss rose while train loss fell — mild overfit at 3 epochs.

> **Where are the weights?** `adapters/` is gitignored (~74 MB of binaries per run, permanent
> in git history). The tracked evidence for a run is `run_records/<run_id>.json`. Restore an
> adapter into `adapters/<run_id>/adapter/` before evaluating or converting it.

After a real run, paste the run-record summary into `04_docs/training_run_log.md` and hand the adapter to Part 3 evaluation.
