# Individual contribution — Thevindu

**Track:** domain LLM / fine-tuning (`model-Thevindu/` on branch `thevindu-dev`).  
**Not claimed:** the live chat agent, resource graphs, Docker auth, or React UI (other members).  
**Scope:** offline dataset → LoRA → fail-closed eval → promote-or-rollback, kept **out of** the student request path so the app stays deployable on CPU.

My individual contribution focused on the **domain model track**: Sri Lankan legal corpus, instruction-pair generation, Qwen 2.5 LoRA fine-tuning, accuracy/groundedness versioning, and the MLOps contract that would let the live app swap a generator later without training inside a chat request. I also merged `main` into `thevindu-dev` so the ML folder can sit beside the integrated frontend/backend without overwriting them.

---

### 1. Architecture and planning

I defined the split between **offline ML** and **online app**: corpus → pairs → LoRA → eval → a `live_model_version` pointer. The app only ever reads that pointer (or keeps the local GGUF / API fallback). The difficulty was that a fine-tune on Colab would make the web app unusable if it ran in-process. I kept `learnmate/` free of PEFT loading, documented HTTP/Gemini swap as two `.env` lines, and used a **branch-per-member** workflow (`thevindu-dev` only; never commit to `main` locally). Integration with `main` was a merge *into* my branch, resolving `.gitignore` and the README split so weights/secrets stayed ignored while product docs from `main` were preserved.

### 2. Corpus and text processing

I built Stage 1 (`preprocess_dataset.py`): extract, drop table-of-contents fragments, section-aware chunks, inherit `section_id` onto continuation chunks, and tag `subject_area` from the **manifest**, not from filename guessing. I assembled a 21-document pilot (`lm-legal-v0.1`): 19 parsed, 1,280 chunks; two scans failed (no text layer) and were not OCR’d. I excluded Black’s Law 1891 (US dictionary, not Sri Lankan law). A challenge was that keyword fallback would have mis-tagged statutes. I made the CSV `subject_area` column authoritative (`verify_manifest.py`). Another challenge was provenance: `documents.gov.lk` URLs later 404’d; I recorded Tier A/B and dead links in the manifest rather than silently treating every PDF as official.

### 3. Training-pair generation (GI-001)

I implemented Stage 2: live `gpt-4o-mini` pairs (Q&A, summary, MCQ) grounded in the excerpt. A spot check found **~38% ungrounded section citations** (model inventing provision numbers). I fixed this with TOC drop, inherited section ids, a citation rule in the prompt, and fail-closed `validate_pairs.py`. After the fix: **2,534 pairs kept, 26 rejected (1.0%)**. The challenge was that a naive “any digits + period” whitelist let inventions through; I narrowed excerpt matching so ordinary numbers were not treated as statute citations.

### 4. Dataset split (GI-002)

Whole-document split left `family_law` and `property_land` with **zero training pairs**. I switched to chapter-group split (`doc_id` + chapter): train 1,590 / val 339 / test 325, every subject in all three splits, plus `test_strict` (280 pairs, whole documents never seen). I **renamed the metrics** (`in_corpus_accuracy` vs `accuracy (document-held-out)`) so chapter leakage could not be read as true generalisation. Six single-document subjects still have no true holdout — a corpus gap, not a splitter bug.

### 5. Fine-tuning

I implemented and ran `finetune_qwen25_lora.ipynb` on Colab T4 (Qwen2.5-1.5B-Instruct, QLoRA, LoRA r=16, 3 epochs, 597 steps, peak 3.39 GB). Challenges: Colab install/version drift, BFloat16 leaking into adapter weights, GradScaler dtype bugs, and T4 VRAM. I added a self-contained precision guard, sized the schedule to the real 1,590-example set (not the 69-example smoke set), and required a **run-record** JSON for every run. Smoke runs stayed labelled smoke. Weights stay gitignored except an evaluation snapshot of the one real adapter on `thevindu-dev`.

### 6. Testing, versioning, and honest failure

I built `evaluate_candidate.ipynb`, `acceptance_thresholds.yaml`, `version_registry.csv`, and `rescore_eval.py`. Live eval vs gpt-4o-mini on both splits: token-F1 looked like a pass (0.717 / 0.836); **LLM-as-judge accuracy was 0.557 / 0.621** (below 0.70). A regex groundedness check over-flagged ~50% of answers (`section 108` vs `108.` in the excerpt); rescoring with the Stage-2 checker gave **0.877 / 0.921**. Latency p95 on sequential T4 generate was ~15–16 s (not serving hardware). I logged **FAIL** on every row and did **not** promote. The challenge was not “train more” — it was measuring the right thing and stopping when the gate failed.

### 7. Integration with `main` and evaluation visibility

I merged `origin/main` into `thevindu-dev` only: union `.gitignore` (`*.log` + weight/secret rules), index README, filled `README-MACHINE-LEARNING.md`. I did not rewrite the live app. For teammate/evaluation checkout I force-added corpus PDFs, `processed_v01/`, eval predictions, and the real adapter on **`thevindu-dev` only**, with an explicit warning not to drag that snapshot onto `main`. Secrets stay in gitignored `.env`.

---

### Overall

I turned a blank ML folder into a complete offline factory: corpus, pairs, LoRA, fail-closed registry, and a promotion checklist — and I **refused to ship a model that lost the judge and the API comparison**. The difficulties were ungrounded citations, an unusable whole-document split, a misleading eval regex, lexical accuracy vs a real judge, Colab/T4 constraints, and merging independently evolved `main` docs without contaminating the app or `main` itself. The live platform keeps local Qwen 2.5-3B + Llama 3.2; a later corpus (`lm-legal-v0.2`) is the path if a domain adapter is ever to pass the gate.
