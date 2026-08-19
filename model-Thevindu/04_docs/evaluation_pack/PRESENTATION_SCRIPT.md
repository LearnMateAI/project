# Presentation script (5–10 minutes)

**You:** Thevindu — domain model / fine-tuning.  
**Live folders:** `integrated-frontend` + `integrated-backend`.  
**Your folders:** `model-Thevindu/`.  
**Do not claim:** you wrote the chat LangGraph or the React app. Credit teammates; own the offline factory and the honest fail.

**Timebox:** ~2 min product + architecture → ~2 min demo → ~5 min **your pipeline** → ~1 min close.  
If time is 5 minutes: skip demo details, keep slides “The two systems”, GI-001, GI-002, numbers, fail, future.

**Before you start:** UI at http://localhost:5173, backend `:8010`, Docker up. Have ChatMessage mode badge limitation in mind — do not promise a badge that is not on screen.

---

## Introduction (~1 min)

Good morning. I am Thevindu. LearnMateAI is a study platform for **Sri Lankan legal education**. A student uploads a statute or lecture PDF, asks questions that should be **grounded in that file**, and generates summaries, key points, MCQs, and practice questions. A **second model**, from a different family, grades what the first wrote before the student sees it.

The target user is a law student on a laptop. Uploaded documents **do not leave the machine** in the default setup: local GGUFs via llama.cpp, MongoDB and Qdrant in Docker.

I will show how the live system is put together, then spend most of this talk on **my contribution**: the offline pipeline that builds a domain LoRA, evaluates it against a written gate, and **refuses to promote** a candidate that failed. That refusal is a design result, not an unfinished demo.

---

## System architecture and tech stack (~1.5 min)

**[Slide: two columns — live vs offline]**

There are two systems that must not be confused.

**Live path.** React 19 and Vite on port 5173 talk JSON + JWT to FastAPI on **8010**. The backend is split on purpose: `app/` is HTTP, auth, and the job queue; `learnmate/` is the engine and knows nothing about users. Routers never touch the database directly; services never raise HTTPException. Slow work — ingest, generate, chat — returns **202 and a job id**. The browser polls. There is **one worker thread** because llama.cpp has a single mutable context; two threads would interleave tokens.

**Models in production today:** Qwen2.5-3B Q4 writes; Llama-3.2-3B Q4 judges; MiniLM embeds; a MiniLM cross-encoder reranks. Chat graph: rewrite → retrieve → generate → evaluate → decide → persist, with one retry.

**My path, offline.** `model-Thevindu/`: legal PDFs → chunks → instruction pairs → LoRA on Qwen2.5-**1.5B** on Colab → eval vs `acceptance_thresholds.yaml` → registry row. The live app would only learn a pointer, via `LEARNMATE_GENERATOR_BACKEND=http` in `learnmate/llm/http_api.py`. We have **not** flipped that switch.

Mongo is on **27018**, Qdrant on **6335**, so we do not share another project’s database.

---

## Live demo walkthrough (~2 min)

Speak only what is on screen. If the backend is down, stay on Home / About / Tour.

**[Open http://localhost:5173/]**  
This is the public home. A visitor can read About and Take a Tour without an account. `/` is Home, not a login wall.

**[Go to Register → create an account]**  
JWT in localStorage. Passwords are bcrypt. `/api/auth/me` validates the token on reload.

**[Documents — upload a small legal PDF, pick a subject]**  
The API returns 202. The row goes Processing to Ready by itself. The file is hashed with SHA-256, so the same PDF is embedded once if two students upload it. Ownership lives in `user_documents`, not on the document.

**[Resources panel — generate Key points, passage scope]**  
Again 202. Watch the progress text — that is the job record in Mongo, not a spinner guessing. Structural checks run first, then the Llama judge, then at most one retry.

**[Open the resource]**  
If the score is not visible, say: “The backend already returns accepted, score, and reasoning; showing that on this page is a known UI gap, not missing evaluation.”

**[Chat — ask something the PDF clearly answers, then something it does not]**  
Retrieval plus rerank. A low retrieval score can fall back to general knowledge. I will be honest: the **mode badge was removed from the chat bubble** even though `turn.mode` is still on the API. That is a frontend omission we should restore.

**[Do not]** open root `frontend/` or start uvicorn on 8000.

---

## My part — pipeline, decisions, results (~4 min)

**[Slide: pipeline]**  
Stage 1 parse and chunk. Stage 2 pairs with a live LLM. Stage 3 chapter split plus a strict document holdout. Fine-tune. Evaluate. Promote only through a checklist.

**Corpus.** 21 files, 19 parsed, 1,280 chunks. Two scans failed — no text layer; I did not OCR them. Subject tags come from the **manifest CSV**, not filename keywords. Black’s Law 1891 was excluded: it is an American dictionary.

**GI-001.** A 40-pair spot check showed about **38% ungrounded section citations**. Fix: drop TOC chunks, inherit `section_id`, citation rule in the prompt, fail-closed `validate_pairs.py`. Full corpus: 2,534 pairs kept, **1.0% rejected**.

**GI-002.** Whole-document split left family law and property with **zero training pairs**. I grouped by document and chapter: 1,590 / 339 / 325, every subject in all three splits, plus 280 pairs of unseen full documents. Those two accuracies are **not the same number**. Chapter-held-out is in-corpus recall. Document-held-out is closer to generalisation. Six subjects still have only one source document.

**Training.** Qwen2.5-1.5B-Instruct, QLoRA, LoRA rank 16, three epochs, 597 steps, Colab T4, peak 3.39 GB, about 94 minutes. Run id `qwen25-lora-20260815-090709`. Smoke runs on 69 synthetic examples are **not** this candidate.

**Eval.** Token overlap looked like a pass: 0.717 and 0.836. An LLM-as-judge, same idea as the live “unsupported claim fails” rule, scored **0.557 and 0.621** — below 0.70. A naive regex called half the answers hallucinations because the excerpt said `108.` and the model said `section 108`. The Stage-2 checker gives groundedness **0.877 / 0.921**. T4 sequential generate was 15–16 seconds p95; that is not a serving number. Versus gpt-4o-mini we lose on accuracy. **Registry: passed=False. Not promoted.**

I will not put this adapter in the request path. More epochs will not fix T4 latency or beat a much larger API on a 21-document pilot. Next corpus work is `lm-legal-v0.2`: at least two text-layer documents per subject.

---

## Challenges, future work, close (~1 min)

The hard problems were **measuring the right thing** and **not shipping anyway**. Citation hallucination in the training data, an illegal whole-document split, a regex that lied about groundedness, and token-F1 that lied about correctness. Each was fixed or renamed in code and lineage, not hidden.

Future work: grow the corpus; diagnose the 0.557 fails on saved predictions before any second train; restore the chat mode badge; fix smoke-test default port 8010. Promotion stays blocked until document-held-out accuracy, groundedness, latency on **target hardware**, and the fallback comparison all pass, with a teammate who did not train the run signing the checklist.

The live product is a local, judged, citation-aware study assistant. The domain factory exists, was run for real, and **failed closed**. That is the result I am defending. Thank you — I welcome questions.

---

## If they interrupt

| They say | You say |
|---|---|
| “So the fine-tune is in production?” | “No. Live generator is Qwen 2.5-3B GGUF. The 1.5B LoRA failed the gate.” |
| “Why 1.5B not 3B?” | “Budget and Colab T4. The live 3B is already the writer. The LoRA was a domain adapter experiment, not a replacement until it wins the gate.” |
| “Show me the loss curve.” | Train 1.038, eval 1.247, 597 steps — loss is not the promotion metric; the registry is. |
