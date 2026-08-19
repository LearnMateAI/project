# Technical evaluation Q&A

Answers are written in first person as you would speak them. Numbers come from `version_registry.csv`, `dataset_lineage.md`, and the live `integrated-*` code. Do not upgrade a FAIL into a pass while answering.

---

## How to use this

- Lead with the decision, then the file, then the number.
- If you did not write the live chat/UI: say so, then explain it accurately. That is stronger than claiming ownership.
- If you do not know a line number, name the module. Guessing line numbers is worse than saying “I would open `graph.py`.”

---

## A. Architectural and design decisions

### A1. Why is the ML folder separate from the FastAPI app?

The live request path cannot train. Colab QLoRA on a 1.5B model took ~94 minutes and needs a GPU. Putting PEFT inside a student chat would make the product unusable on CPU.

`model-Thevindu/` is an **offline factory**: corpus → pairs → LoRA → eval → registry. The app is supposed to read only a **promoted pointer**. That contract is written in `05_mlops_workflow/mlops_lifecycle.md`. We have **not** written a live pointer because the candidate failed.

The swap, when a later candidate passes, is already implemented as two `.env` lines: `LEARNMATE_GENERATOR_BACKEND=http` and `LEARNMATE_GENERATOR_API_URL`. Agents call `get_generator_llm()` in `learnmate/llm/registry.py` and never learn which backend answered.

### A2. Why FastAPI + React rather than a notebook demo for the product?

The product is a **multi-user study platform**: JWT accounts, document libraries, async jobs, RAG over a user’s PDFs. That needs HTTP, a database, and a UI. The notebook is the right tool for **training**, which is why Part 2 is `finetune_qwen25_lora.ipynb` on Colab, not a FastAPI route.

### A3. Why split `app/` from `learnmate/`?

`app/` is HTTP: JWT, routers, the job queue. `learnmate/` is the engine: ingest, RAG, graphs, llama.cpp. The engine **never imports FastAPI**. Services raise `ValueError`, `NotFound`, `AccessDenied`, `StorageUnavailable`. `app/errors.py` maps those to 400 / 404 / 403 / 503. That lets the **same engine** run from the worker thread, where there is no request object.

Routers do not touch Mongo. Services do not raise `HTTPException`.

### A4. Why MongoDB and Qdrant, not Postgres + pgvector?

Mongo holds documents, pages, sessions, jobs, generated resources, evaluations, users. The shape is nested (a resource with MCQ items, a job with progress) and we did not need SQL joins for the core loop.

Qdrant is the vector store for retrieval. Vectors are **derived**: if Qdrant is wiped, we re-embed from page text already in Mongo. `docker-compose.yml` documents that on purpose.

Host ports are **27018** and **6335**, not 27017 / 6333, because this machine already runs other projects on the defaults. Sharing a server would mean sharing a `docker compose down -v`.

I did not choose those databases as a personal preference for the ML track; I designed around them. My corpus never writes to Qdrant. Stage 1 chunks live in `processed_v01/` JSONL.

### A5. Why one worker thread, not a pool?

`app/jobs/worker.py` is explicit: `llama_cpp.Llama` has **one mutable context**. Two threads interleave tokens and corrupt both replies. Sentence-transformers has the same issue under default Torch threading. A `ThreadPoolExecutor(max_workers=4)` would produce **quietly wrong answers**, not a crash.

Locks sit next to what they protect: `_LLAMA_LOCK` in `llamacpp.py` for the whole generation; `_LOAD_LOCK` in `runtime.py`, `embeddings.py`, `rerank.py` for construction. The worker and the boot warm-up thread can overlap on I/O, but not on the model.

### A6. Why 202 + job polling instead of a long HTTP request?

Ingest, resource generation, and chat can take minutes on a 3B CPU GGUF. Holding an HTTP connection that long is fragile. The API writes a job to Mongo **before** enqueueing, returns `{job_id}`, and the UI polls. `useJob.js` aborts polling on unmount so a navigated-away page does not set state on a dead tree.

### A7. Why Qwen as generator and Llama as judge?

`registry.py`: a judge that shares the generator’s weights rates its own style highly and the retry loop stops firing. Live: **Qwen2.5-3B-Instruct Q4** writes; **Llama-3.2-3B-Instruct Q4** judges. Offline eval used the same idea: LLM-as-judge with `gpt-4o-mini` against the CHAT_GROUNDED rule (“unsupported claim = fail”).

### A8. Why Qwen2.5-1.5B for the LoRA, not the live 3B?

Budget and Colab T4. Peak VRAM on the real run was **3.39 GB**. The live 3B GGUF is already the production writer. The LoRA was a **domain adapter experiment** on a smaller instruct checkpoint. Promoting it would *replace* a 3B general model with a 1.5B specialist that **lost** the judge and the API comparison. That would be a product regression.

### A9. Why LoRA / QLoRA instead of full fine-tune?

Full fine-tune of even 1.5B on T4 is not realistic for this budget. LoRA rank 16 updates a small adapter. The base stays Qwen2.5-1.5B-Instruct. If the adapter is bad, we throw it away and the base (or the live 3B GGUF) still exists. That matches fail-closed promotion.

### A10. Why not train inside LangGraph?

The chat graph is `rewrite → retrieve → generate → evaluate → decide → persist` (`learnmate/chat_agent/graph.py`). It is **one user turn**. Training is a scheduled offline job. Mixing them would block every student behind a GPU we do not have on the laptop.

### A11. Why chapter split instead of a random pair shuffle?

Legal text is highly duplicated inside a statute. Shuffling pairs would put two questions about the same paragraph in train and test. We group by `(doc_id, chapter)`. That is still leaky — chapters of one Act can appear in both splits — which is why we also keep `test_strict`. Random shuffle would have been the weakest of the three.

### A12. Why keep the live generator as llama.cpp GGUF rather than always calling OpenAI?

Default product goal: documents stay on the machine. Gemini / HTTP are **degradation paths** (`LEARNMATE_GENERATOR_BACKEND=gemini` or `http`). The MLOps doc requires fallback even after a successful promote. We used `gpt-4o-mini` for Stage 2 pair generation and for eval comparison because that is an **offline** cost, not a per-student chat cost.

### A13. Why is `components-Dinura/` still in the repo?

It is the engine **origin**. The live copy is `integrated-backend/learnmate/`. Developing in the old folder would not change the running app. Same for root `frontend/` and `backend/` — stale. Demo only `integrated-frontend` (5173) and `integrated-backend` (8010).

### A14. Why JWT in localStorage, not httpOnly cookies?

Current design: Axios attaches `Authorization: Bearer` from `localStorage`. Tokens last 24 hours; a 401 interceptor wipes the session and hard-redirects to `/login` (`client.js`). A known limitation: that interceptor can also fire on a **failed login** 401 and is not scoped to “already authenticated” calls. I would not defend it as ideal; I would name it as a frontend hardening item.

---

## B. Implementation and code logic

### B1. Walk through one chat turn.

1. UI posts to the chat router; service enqueues a job (`app/routers/chat.py`, `app/services/chat.py`).
2. Worker runs the compiled graph from `get_chat_graph()`.
3. **rewrite** — standalone query for retrieval.
4. **retrieve** — vector search (optionally rerank). If top score ≥ threshold → `mode=pdf`; else `mode=general` (`retrieve.py`). The decision is a **number**, not a second LLM call.
5. **generate** — Qwen writes, with retrieved chunks only in pdf mode.
6. **evaluate** — Llama scores against `CHAT_GROUNDED` or `CHAT_GENERAL` in `evaluator/rubrics.py`.
7. **decide** (`routing.py`) — pass → persist; no critique or score &lt; threshold−25 → persist anyway; else regenerate once; if `attempt >= max_attempts` persist the failed reply so the user is not left in silence. `accepted` on the turn tells the truth.
8. **persist** — history in Mongo.

### B2. How does retrieval actually rank?

Wide cosine search (`RERANK_CANDIDATES`), then MiniLM cross-encoder to `TOP_K`. Weak rerank hits below `RERANK_THRESHOLD` are dropped, but the **best** chunk is always kept so `top_score` can still choose pdf vs general. If the reranker fails to load mid-turn, we fall back to cosine scores rather than failing the turn.

Embeddings: `all-MiniLM-L6-v2`. Reranker: `ms-marco-MiniLM-L-6-v2`.

### B3. How does document upload avoid embedding the same PDF five times?

`documents` is keyed by **SHA-256 of the bytes**, unique index. `user_documents` is `{user_id, doc_id, filename, subject}` (`ownership.py`). Five students uploading the same file share one embedding job. Filename and subject are **per user** on purpose. Access checks always go through `user_documents`, never a `owner_id` on the document.

### B4. What does `validate_pairs.py` actually match?

Citations in the **answer** only count when labelled: `section`, `article`, `chapter`, `rule`, `order`, etc. Ordinary numbers (“three months”) are ignored.

The **excerpt** is searched more broadly: labelled citations, line-initial `147.`, marginal-note `5. (1)`, alphanumeric `153A`. Inherited `section_id` from Stage 1 is in the allow-list so a continuation chunk is not punished for not restating the number.

An earlier whitelist of “any digits + period” scored 1/40 against a hand review of 15/40 inventions. We narrowed it. Six cases are pinned in `test_validate_pairs.py`.

### B5. How does Stage 2 generate pairs?

`generate_training_pairs.py` + `scripts/stage2_generate_pairs.py`. Live `gpt-4o-mini`, two pairs per chunk (Q&amp;A / summary / MCQ mix). The prompt includes the inherited section id or an instruction not to invent one. Each pair is passed through `check_pair` before write. Fail-closed: 26 of 2,560-ish drafts dropped (**1.0%**), 2,534 kept.

### B6. How does the splitter pick `test_strict`?

`pick_strict_holdout` in `split_dataset.py`: per subject with ≥2 documents, reserve the **smallest** qualifying document, but only if ≥3 chapter-units remain for train/val/test. Seed 42.

Held out: civil procedure (Mediation Act No. 21), constitutional (21st Amendment), contract (Sale of Goods), criminal procedure (Primary Courts' Procedure). **family_law skipped** — only two documents; holding one out recreates GI-002.

Six subjects still have a single source document and therefore **no** true generalisation test: `administrative_public`, `company_commercial`, `criminal_law`, `evidence`, `intellectual_property`, `property_land`.

### B7. What happened in the training notebook?

`02_finetuning/finetune_qwen25_lora.ipynb`. Qwen2.5-1.5B-Instruct, QLoRA 4-bit, LoRA r=16, 3 epochs, 597 optimizer steps, Colab T4, ~93.7 min, train/eval loss **1.038 / 1.247**, run id `qwen25-lora-20260815-090709`.

Earlier runs `…052502` and `…054543` are **smoke on 69 synthetic examples**. I will not quote their loss as domain performance.

Practical bugs we hit: Colab package drift, BFloat16 leaking into adapter weights, GradScaler dtype. The notebook has a precision guard. Every run writes `run_records/*.json`.

### B8. Why rescore instead of retraining?

The first live eval used a naive string-set groundedness check. It treated `section 108` vs excerpt `108.` as a hallucination (~50% “ungrounded”). That failed the 0.85 gate **incorrectly**. `rescore_eval.py` re-reads **saved predictions** with `validate_pairs.check_pair` and optionally an LLM judge. No GPU. Groundedness moved to **0.877 / 0.921**. Accuracy under the judge moved **down** to **0.557 / 0.621**. Both facts matter: we fixed the metric, we did not shop for a pass.

### B9. How would a passing adapter enter production?

1. Registry `passed=True` on **document-held-out** accuracy, plus groundedness, latency on **named serving hardware**, fallback comparison.
2. Signed `promotion_checklist.md` (four-eyes: someone who did not train the run).
3. Serve the adapter (GGUF via `scripts/build_finetuned_gguf.py`, or OpenAI-compatible HTTP).
4. Set `LEARNMATE_GENERATOR_BACKEND` to `llamacpp` or `http`. Restart. Agents unchanged.

We are not on step 3.

### B10. Resource generation graph?

Separate LangGraph in `learnmate/resource_agent/`. Structural checks first (`mcq_rules.py`, `text_rules.py`) so the 3B judge is not asked to count to four. Then Llama rubric (`MCQ`, `KEYPOINTS`, `SUMMARY`, `PRACTICE_QSN`). Retry at most once, same “persist anyway” idea. UI currently **does not show** `accepted` / `score` / `reasoning` on `ResourceView.jsx` even though the API returns them — a known gap.

### B11. Frontend job hook — anything subtle?

`useJob.js`: one `AbortController` per run; abort on unmount; `run` **does not rethrow** — failures land in `error`. Callers must check the resolved value. Progress text is the Mongo job’s `progress.message`, not a fake spinner.

---

## C. Data integrity and state management

### C1. How do you know train and test_strict do not overlap?

Lineage check: no strict-holdout `doc_id` in train/val/test; no duplicate `pair_id`; no chunk in more than one split. Chapter split **does** allow the same statute in train and test at chapter granularity — that is why the metrics have different names.

### C2. Why two accuracy numbers?

| Registry field | Split | What it measures |
|---|---|---|
| `in_corpus_accuracy (chapter-held-out)` | `test.jsonl` (325) | Chapters of statutes partly seen in training |
| `accuracy (document-held-out)` | `test_strict.jsonl` (280) | A whole statute never seen |

`acceptance_thresholds.yaml` v2 says the **0.70 bar was written against the second**. Clearing 0.70 on chapter-held-out alone is not a promotion. Token-F1 was 0.717 / 0.836 — the first looks like a pass if you ignore the definition. LLM-judge is 0.557 / 0.621 — both fail 0.70.

### C3. Subject tags — filename or CSV?

Manifest `subject_area` is authoritative (`verify_manifest.py`). Filename keywords would mis-tag. Example: `Mediation Boards Act no 21.pdf` is actually **Mediation (Special Categories of Disputes) Act No. 21 of 2003**; subject stays `civil_procedure`. `Mediation Boards Act no 27.pdf` is a **misnamed scan** — no Act No. 27 of that name; likely Act No. 72 of 1988. It never entered `lm-legal-v0.1` because it has no text layer.

### C4. Provenance / dead URLs?

`documents.gov.lk` `/view/act/...` paths 404 after a site rebuild. Manifest marks DOC-020, DOC-028, DOC-035 (and a provenance URL on DOC-026) stale. We do not pretend every PDF is a live official download. Tier A vs Tier B is in the manifest and `mentor_pilot_disclosure.md`.

### C5. Mongo vs frontend state?

Server state is Mongo (and Qdrant for vectors). React state is per-page plus `localStorage` token/user. `useJob` is local hook state. Settings currently write `learnmate_prefs` that **nothing reads** — I will not claim a working preference system. Analytics can ignore `stats.evaluation` even though the API computes it.

### C6. What if two users generate resources on the same shared document?

The document bytes and vectors are shared. Generated resources are stored per generation (tied to the user/session), not overwritten on the canonical PDF. Ownership still gates who may start a job on that `doc_id`.

### C7. Jobs survive a browser refresh?

Yes — the job record is in Mongo. Polling is “is this id done?”, not an in-memory promise. Refresh loses the React hook until the UI looks the job up again; the work continues on the worker.

---

## D. Error handling and edge cases

### D1. Scanned PDF, no text layer?

Engine raises `ValueError`: no extractable text; scanned PDFs need OCR. `errors.py` → **400**. The live app does **not** OCR. In the corpus track I also refused OCR on two scans; text-layer replacements were identified but **not** mixed into `lm-legal-v0.1`.

### D2. Password-protected PDF?

`app/services/documents.py` fails **immediately** with 400, not a job that dies a minute later.

### D3. File too large?

Frontend `DocumentsCard.jsx` checks `MAX_MB` before upload. (Confirm the constant on screen — typically 10 MB.)

### D4. Mongo or Qdrant down?

`StorageUnavailable` / `QdrantUnavailable` → **503** with the URI that was tried. Unhandled exceptions → **500** with a vague body; traceback only in the server log.

### D5. Invalid JWT / expired token?

401 → Axios interceptor clears `token` and `user`, `window.location.replace("/login")` unless already on `/login`. Honest caveat: a failed **login** 401 can look like “session expired” if that path is not excluded.

### D6. Chat retrieval finds nothing useful?

`mode=general`. Rubric switches to `CHAT_GENERAL` (relevance/coherence, not groundedness). The UI **used to** show a mode badge; `ChatMessage.jsx` currently does not. Backend still returns `turn.mode`. I will say that in the demo rather than invent a badge.

### D7. Judge fails to return a verdict?

`decide` skips retry (“no actionable critique”) and persists. Better a possibly-weak answer than an infinite loop.

### D8. Score far below threshold?

If `score < threshold - 25`, skip retry — regeneration will not salvage it. Persist, `accepted=false`.

### D9. Stage 2 API error during pair generation?

`lm-legal-v0.1` recorded **0 API errors**. The pipeline is fail-closed on **grounding**, not on “keep the pair anyway.” Smoke path `--mock` exists so CI does not need a key.

### D10. What if someone loads the failed adapter into `.env` anyway?

Technically `http` or a merged GGUF would answer. Processually that violates the checklist. I would refuse. Serving a model that lost 0.557 vs 0.871 against the fallback is worse than keeping the 3B GGUF.

### D11. Latency gate on T4 — is that fair?

`acceptance_thresholds.yaml` says a Colab T4 sequential 4-bit number **does not transfer** to unspecified serving hardware. p95 16.4 s / 14.9 s fails 8 s on **eval hardware**. Even if we moved serving to llama.cpp 3B-class later, we would re-measure there. I do not argue the T4 number as production latency.

### D12. Empty model answer?

`check_pair`: empty output is ungrounded. Counts against groundedness 0.85 / hallucination 0.15.

### D13. Student asks something harmful / off-policy?

I should not overclaim a safety stack we did not build. The live judge rubrics are about **groundedness and resource quality**, not a full safety classifier. If asked, say that is future work, not a hidden feature.

### D14. Race: poll before job exists?

`enqueue` writes Mongo **first**, then `Queue.put`. Immediate poll should 200, not 404.

---

## E. Questions aimed at *your* track (expect these)

### E1. “So the fine-tune is in production?”

No. Live generator is **Qwen2.5-3B Q4 GGUF**. Candidate `qwen25-lora-20260815-090709` is **passed=False** on every registry row.

### E2. “Token-F1 was 0.72 — why fail?”

Token-F1 rewards lexical overlap with the gold assistant turn. A legally wrong sentence that shares nouns still scores. The live product fails **unsupported claims**. LLM-as-judge is the metric that matches that rule: **0.557 / 0.621**.

### E3. “Did you just make the eval harder until it failed?”

Opposite chronology. Naive regex made **groundedness** look worse than it was. After the correct checker, groundedness **passed**. The judge then showed **accuracy** was the real miss. We published both.

### E4. “Why not train more epochs?”

Eval loss 1.247 vs train 1.038 already suggests we are not underfit in the naive sense. The miss is **judge accuracy and beating gpt-4o-mini**, plus corpus coverage (six single-doc subjects). More epochs will not add a second Evidence Act.

### E5. “Is 21 documents enough?”

It is a **pilot** (`lm-legal-v0.1`), disclosed as such. Enough to run the factory and catch GI-001/GI-002. Not enough to claim a production domain model. Next: `lm-legal-v0.2`, ≥2 text-layer documents per subject.

### E6. “Black’s Law?”

Excluded. 1891 American dictionary, 11 MB, would have dominated chunk count, not Sri Lankan law.

### E7. “Did you OCR?”

No. Two scans failed Stage 1. Replacements identified (Arbitration Act text-layer PDF; Mediation Boards 2024 consolidation). Not mixed into v0.1. OCR would have taught the model scan typos.

### E8. “Smoke vs real — how do I tell?”

Smoke: `lm-legal-smoke-v1/v2`, six synthetic PDFs, 69 examples, run ids `…052502` and `…054543`. Real: `lm-legal-v0.1`, run `…090709`. Honesty board in `model-Thevindu/README.md`.

### E9. “model_card.md still says TEMPLATE?”

Yes. Docs are **partial**. I would rather leave a template than fill a card that implies a promoted model. Filling it with FAIL numbers is a fair post-viva cleanup.

### E10. “Who signs promotion?”

`promotion_checklist.md` — four-eyes. I cannot sign my own run into production.

---

## F. Questions you should *invite* if the panel is quiet

1. Why `in_corpus_accuracy` and `accuracy` must never be averaged.
2. Why TOC chunks caused the Audit Service Commission hallucination (GI-001).
3. Why family_law has no `test_strict` row.
4. Why the worker is one thread (correctness, not just CPU).
5. What two `.env` lines would flip after a future pass — and why we have not flipped them.

---

## G. One-sentence fallbacks

| Topic | Line |
|---|---|
| Product | Local, judged, citation-aware study assistant for Sri Lankan law students. |
| Your job | Offline factory; fail-closed; not in the request path. |
| Result | Real LoRA, real eval, **not promoted**. |
| Next | Bigger corpus, diagnose 0.557 fails on saved predictions, then consider a second train. |
| Live models | Qwen 3B writes, Llama 3B judges, MiniLM retrieves. |
