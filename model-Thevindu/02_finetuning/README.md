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
| Full GPU training run on Colab | **Not executed in this repo** (needs GPU + HF download; ~budget-sensitive) |

After a real run, paste the run-record summary into `04_docs/training_run_log.md` and hand the adapter to Part 3 evaluation.
