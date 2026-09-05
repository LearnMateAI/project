# Promotion checklist — thevindu-models drop-in (not a LoRA)

Same four-eyes idea as `model-Thevindu/03_testing_and_versioning/promotion_checklist.md`.
A comparison GGUF or embedder moves to a live pointer only when every box is checked.

Candidate id: `______________________________`
Evaluator: `______________________________`
Date: `______________________________`

---

## A. Preconditions

1. [ ] GGUF (or HF embedder/reranker) is on disk and, for GGUF, magic bytes are `GGUF`.
2. [ ] Live `.env` and `selectable_default` were **not** edited to run the eval.
3. [ ] Pairing rule held: generator and judge are different families.
4. [ ] `testing/acceptance_thresholds.yaml` version used is recorded below.

## B. Evaluation

5. [ ] Ran `scripts/eval_components.py` through the **live** `chat_agent` / `evaluator` (or retrieve script for embedders).
6. [ ] Raw `results/components.json` (and `results/real_pdf.json` for retrieve) backs every number.
7. [ ] Stated decision rule applied in a sentence, not only a table cell.
8. [ ] Every latency number names this laptop CPU.

## C. Retrieve-specific

9. [ ] Embedder/reranker verdict is based on the **real PDF**, not the toy fixture.
10. [ ] No mixed-family vectors were written to Qdrant.

## D. Promote

11. [ ] Second teammate reviews the per-model `RESULTS.md` + this checklist (four-eyes).
12. [ ] Production change is a reversible pointer / env value only.
13. [ ] Previous live id recorded as rollback: `________________`.

## E. Do not

- Do not merge `thevindu-models` to `main` as a silent model change.
- Do not promote on Colab T4 numbers or retrieve-only ms labeled as chat p95.

---

## Sign-off

| Role | Name | Initials | Date |
|------|------|----------|------|
| Evaluator | | | |
| Reviewer | | | |

**Notes / thresholds version:**

```
(write here)
```
