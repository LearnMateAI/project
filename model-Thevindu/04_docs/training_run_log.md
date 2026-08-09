# Training run log (operational)

Separate from the version registry (eval pass/fail). One row per training attempt.

| run_id | date_utc | dataset_version | base_model | hardware | duration | approx_cost_usd | final_train_loss | final_eval_loss | outcome | artifact_path | notes |
|--------|----------|-----------------|------------|----------|----------|-----------------|------------------|-----------------|---------|---------------|-------|
| *(none yet)* | | | | | | | | | | | No GPU training committed; notebook ready in `02_finetuning/` |

Budget reminder: prefer Qwen2.5-1.5B/3B + QLoRA on free/cheap GPU tiers.
