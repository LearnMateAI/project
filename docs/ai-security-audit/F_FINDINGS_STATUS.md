# F-findings: what was wrong, what “correct” means, what we shipped

This is the correctness map for findings **F-01–F-14**. A finding is **correct** when
the failure mode in the audit can no longer happen on the default (production) path,
and a test or eval can show it.

| ID | Severity | Status | Correctness (pass condition) |
| --- | --- | --- | --- |
| F-01 | High | **Fixed** | `evaluate=false` from a student does **not** skip the judge unless `LEARNMATE_ALLOW_CLIENT_EVALUATE=1`. |
| F-02 | High | **Fixed** | Retrieved PDF text is inside `<retrieved_context>` and labelled untrusted data. A planted “say PWNED” line is data, not a system rule. |
| F-03 | High | **Fixed** | Document-bound chat with no useful chunks **abstains** (canned “I could not find this…”) and does **not** call the generator. |
| F-04 | High | **Fixed (offline)** | 15-item golden set + `eval/golden_rag.py --compare`. Faithfulness 0.667 → 1.0; OOS invented-fact rate 1.0 → 0.0. |
| F-05 | Medium | **Fixed** | History is a `<conversation_history>` block inside the user turn, capped at 500 chars, not extra Human/AI messages after the system prompt. |
| F-06 | Medium | **Fixed** | The judge sees the **same** `contexts` list the generator used (no `[:2]`). |
| F-07 | Medium | **Fixed** | Per-user rate limits (429), chat job timeout 180s, cheap input refuse for self-harm / bomb how-to / exam scrape. |
| F-08 | Medium | **Fixed** | Public `/api/health` has no `mongodb://` URI, no disk model path, no Qdrant URL. |
| F-09 | Medium | **Fixed** | Citation chips require word overlap between the **reply** and the chunk. Retrieved-but-unused pages are dropped. |
| F-10 | Medium | **Fixed** | Whole-document groups run Gate 1 only; the LLM judge runs **once** on the pooled set. |
| F-11 | Medium | **Partial → shipped** | Turn `meta.trace` + `prompt_version`; `POST /api/chat/turns/{id}/feedback`; UI “Helpful / Not helpful”. Not LangSmith. |
| F-12 | Low | **Fixed** | `PROMPT_VERSION = chat-grounded.v2` stored on every assistant turn. |
| F-13 | Low | **Fixed** | `ChatAgent.ask` raises if `user_id` is set and `doc_id` is missing (no whole-corpus search). |
| F-14 | Low | **Fixed** | Settings and resource “skip review” checkboxes removed. Review is server policy. |

## Why each High fix is “correct”

**F-01 (policy, not a client flag).**  
Wrong: a student (or a patched frontend) sent `"evaluate": false` and Gate 2 never ran.  
Correct: `resolve_evaluate()` always returns `True` in production. Lab/CI can opt in with an env flag. The judge is a **server policy**, like auth.

**F-02 (indirect injection).**  
Wrong: chunk text was pasted as `Context:` and the model could treat a line in the PDF as an instruction.  
Correct: XML delimiters + “untrusted DATA” in the system prompt. Resource prompts say the same about the passage.

**F-03 (abstention vs hallucination).**  
Wrong: weak retrieve → `GENERAL_SYSTEM` → Qwen invents law; the judge was skipped.  
Correct: if the session has a `doc_id` and no chunks, return a fixed refuse and skip the LLM. CLI without a document still uses general mode.

**F-04 (you can measure it).**  
Wrong: no golden set on `main`.  
Correct: offline eval that replays pre-fix vs current policy. Those numbers are the interview story.

## Medium / Low in one line

- **F-05** stops “Ignore the PDF” in turn 1 from sitting in the instruction slot for turn 2.  
- **F-06** stops the judge grading a different evidence set than the student saw.  
- **F-07** stops one account wedging the single worker, and blocks a few clearly unsafe asks before a 60s job.  
- **F-08** stops recon via health.  
- **F-09** stops “Cited p.12” when the reply never used that page.  
- **F-10** stops paying ~25s of judge **per group** on a 40-question book.  
- **F-11** lets a downvote land in Mongo so you can add it to the golden set later.  
- **F-12** tells you which prompt wording produced a stored reply.  
- **F-13** is defense in depth: the engine refuses a logged-in ask with no document filter.  
- **F-14** removes a switch that did nothing (or would have undone F-01).

## What is still not “fully correct”

- Live MiniLM + Qdrant + GGUF p95 is **not** what `golden_rag.py` measures (harness is lexical + policy).  
- Rate limits are **in-process**; two server processes would each have their own bucket.  
- Input guard is a small regex list, not a toxicity model. Legal words like “murder” in a criminal-law question are still allowed.  
- Feedback is stored; nothing yet auto-appends downvotes into `golden.json`.  
- No LangSmith/Phoenix traces.
