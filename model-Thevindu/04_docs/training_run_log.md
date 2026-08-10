# Training run log (operational)

Separate from the version registry (eval pass/fail). One row per training attempt.

| run_id | date_utc | dataset_version | base_model | hardware | duration | approx_cost_usd | final_train_loss | final_eval_loss | outcome | artifact_path | notes |
|--------|----------|-----------------|------------|----------|----------|-----------------|------------------|-----------------|---------|---------------|-------|
| qwen25-lora-20260810-052502 | 2026-08-10T05:50:42Z | lm-legal-smoke-v1 | Qwen/Qwen2.5-1.5B-Instruct | Colab T4 (fp16 QLoRA) | ~25 min | 0.00 (free tier) | 1.7805 | 1.3199 | completed — pipeline smoke-test only, NOT a promotion candidate | `02_finetuning/adapters/qwen25-lora-20260810-052502/adapter` (local, gitignored) | First successful end-to-end Colab run after fixing install/version drift, BFloat16-in-LoRA leak, and fp16 GradScaler dtype bugs. Trained on the 69-example synthetic smoke set, not the real legal corpus — proves the notebook works, does not validate model quality. Do not promote. |

Budget reminder: prefer Qwen2.5-1.5B/3B + QLoRA on free/cheap GPU tiers.
