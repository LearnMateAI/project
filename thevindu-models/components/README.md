# Components — same surfaces as `components-Dinura` and `integrated-backend`

The live app does **not** have a Qwen class and a Llama class. `components-Dinura/learnmate`
and `integrated-backend/learnmate` share one `chat_agent/` and one `evaluator/`. Which
family loads is a GGUF path / `model_id`. This folder is that contract for the
`thevindu-models` bake-off.

We do **not** fork twenty agent files per candidate. A fork would drift from the app
the drop-in has to survive in. Each model folder instead has the **same filenames** as
Dinura (`chat_agent/generate.py`, `chat_agent/evaluate.py`, `evaluator/judge.py`, …)
and those files **re-export the live integrated-backend modules**, binding only the
candidate id. That is the replacement: swap the previous model in, keep the component.

```
components-Dinura/learnmate/     ← original decomposed library
integrated-backend/learnmate/    ← fully-wired app copy (streaming, timings, model_id)
thevindu-models/<role>/<id>/     ← same file names, live imports, one model bound
```

## How a swap is tested

`scripts/eval_components.py` loads each candidate **in process**:

| Role | Live component used | What is replaced |
|------|---------------------|------------------|
| Generator | `chat_agent/generate.py` + `resource_agent` MCQ task | `model_id` in `ChatState` / `ResourceState` |
| Judge | `evaluator/judge.py` + `prompt.py` + `rubrics.py` + `verdict.py` | `Judge(llm=candidate)` — `.env` judge stays Llama |
| Embeddings / rerank | `chat_agent/retrieve.py` + `llm/embeddings.py` + `llm/rerank.py` | in-memory vectors only; Qdrant / `.env` untouched |

Never the same family as generator and judge in one process. Never edit
`selectable_default` or `.env` for this eval.

## Testing docs (same idea as `model-Thevindu/03_testing_and_versioning`)

Each candidate folder also has:

| File | Counterpart |
|------|-------------|
| `acceptance_thresholds.yaml` | `model-Thevindu/03_testing_and_versioning/acceptance_thresholds.yaml` |
| `promotion_checklist.md` | `model-Thevindu/03_testing_and_versioning/promotion_checklist.md` |
| `model_card.md` | `model-Thevindu/04_docs/model_card.md` |
| `version_registry.csv` | `model-Thevindu/03_testing_and_versioning/version_registry.csv` |
| `RESULTS.md` | this track's per-model score sheet |

Shared contract: `testing/acceptance_thresholds.yaml` and `testing/version_registry.csv`.
