# Promotion checklist — LearnMateAI domain adapter

Use this checklist **literally**. A candidate moves to production only when every box is checked. The live application should learn **only** the new live model version id — never the training procedure.

Candidate id: `______________________________`  
Evaluator: `______________________________`  
Date (UTC): `______________________________`

---

## A. Preconditions

1. [ ] Adapter directory exists and contains LoRA weights (`adapter_model.safetensors` / `adapter_config.json` or equivalent).
2. [ ] `run_record.json` is present **beside** the adapter and matches `02_finetuning/run_records/<run_id>.json`.
3. [ ] `run_record.json` lists `dataset_version`, hyperparameters, and `final_train_loss` / `final_eval_loss`.
4. [ ] Test split used for evaluation is the Stage 3 held-out set for that same `dataset_version` (no peeking at train).
5. [ ] `acceptance_thresholds.yaml` version used is recorded in notes below.

## B. Evaluation

6. [ ] Ran `evaluate_candidate.ipynb` with `dry_run: false`.
7. [ ] Accuracy ≥ threshold.
8. [ ] Groundedness ≥ threshold **and** hallucination rate ≤ threshold.
9. [ ] Latency p95 ≤ threshold on the intended serving hardware (or documented equivalent).
10. [ ] Fallback comparison completed against the configured production fallback model (Gemini API or equivalent).
11. [ ] Fallback comparison rule passed (see thresholds file).
12. [ ] `version_registry.csv` has a new row with `passed=True` for this candidate.

## C. Staging (offline — not in the request path)

13. [ ] Candidate artifact copied to the staging model store / object path used by the team.
14. [ ] Staging pointer updated to this candidate id (separate from production pointer).
15. [ ] Smoke chat in staging: one statutory Q&A, one MCQ, one “insufficient excerpt” refusal.
16. [ ] Confirmed app still works if the fine-tuned endpoint is killed (fallback path).

## D. Promote

17. [ ] Second teammate reviews registry row + this checklist (four-eyes).
18. [ ] Production live-model pointer updated **only** to the candidate id / artifact URI.
19. [ ] Previous live version id recorded as rollback target: `________________`.
20. [ ] Entry added to `04_docs/training_run_log.md` and `04_docs/dataset_lineage.md` (model version linked).

## E. Monitor (first 48 hours)

21. [ ] Watch fallback rate, error rate, and p95 latency daily.
22. [ ] Spot-check 10 live answers for hallucination against retrieved sources.
23. [ ] If any red flag: execute rollback to previous live version (step 19) before debugging.

---

## Sign-off

| Role | Name | Signature / initials | Date |
|------|------|----------------------|------|
| Evaluator | | | |
| Reviewer | | | |

**Notes / thresholds version / exceptions:**

```
(write here)
```

**Rule:** No exceptions that skip fallback comparison or run-record presence. Budget pressure is not a reason to promote a failing candidate — keep Gemini fallback as the live path instead.
