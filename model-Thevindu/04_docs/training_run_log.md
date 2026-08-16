# Training run log (operational)

Separate from the version registry (eval pass/fail). One row per training attempt.

| run_id | date_utc | dataset_version | base_model | hardware | duration | approx_cost_usd | final_train_loss | final_eval_loss | outcome | artifact_path | notes |
|--------|----------|-----------------|------------|----------|----------|-----------------|------------------|-----------------|---------|---------------|-------|
| qwen25-lora-20260810-052502 | 2026-08-10T05:50:42Z | lm-legal-smoke-v1 | Qwen/Qwen2.5-1.5B-Instruct | Colab T4 (fp16 QLoRA) | ~25 min | 0.00 (free tier) | 1.7805 | 1.3199 | completed — pipeline smoke-test only, NOT a promotion candidate | `02_finetuning/adapters/qwen25-lora-20260810-052502/adapter` (local, gitignored) | First successful end-to-end Colab run after fixing install/version drift, BFloat16-in-LoRA leak, and fp16 GradScaler dtype bugs. Trained on the 69-example synthetic smoke set, not the real legal corpus — proves the notebook works, does not validate model quality. Do not promote. |
| qwen25-lora-20260813-054543 | 2026-08-13T05:48:58Z | lm-legal-smoke-v1 | Qwen/Qwen2.5-1.5B-Instruct | Colab T4 (fp16 QLoRA) | ~10 steps | 0.00 (free tier) | 1.5641 | 1.1592 | completed — second smoke on the same synthetic set, NOT a promotion candidate | `02_finetuning/adapters/qwen25-lora-20260813-054543/adapter` (local, gitignored) | Repeat of the old notebook on 69/15 synthetic examples. Do not promote. |
| qwen25-lora-20260815-090709 | 2026-08-15T10:47:34Z | lm-legal-v0.1 | Qwen/Qwen2.5-1.5B-Instruct | Colab T4 (fp16 QLoRA, peak 3.39 / 14.6 GB, 597 steps, 93.7 min) | 93.7 min | 0.00 (free tier) | 1.0377 | 1.2467 | evaluated — FAILED both gates; do not promote | `02_finetuning/adapters/qwen25-lora-20260815-090709/adapter` (local, gitignored) | First real-corpus eval. Naive regex groundedness 0.498/0.586; `validate_pairs` rescore 0.877/0.921 (clears 0.85). Still FAIL: T4 p95 16.4s/14.9s vs 8s bar, and token-F1 loses to gpt-4o-mini (0.717 vs 0.871; 0.836 vs 0.918). LLM-as-judge accuracy not yet run (rotate leaked key first). |

Budget reminder: prefer Qwen2.5-1.5B/3B + QLoRA on free/cheap GPU tiers.
