# Evaluation pack — Thevindu

Open these for the university viva. They are grounded in the **current repo** (live `integrated-*` app + offline `model-Thevindu/`). They do **not** claim the LoRA is in production.

| File | What it is |
|------|------------|
| [SLIDES.html](SLIDES.html) | Full slide deck (open in a browser). Arrow keys / space to advance. `N` toggles speaker notes. Print to PDF if the panel wants a handout. |
| [PRESENTATION_SCRIPT.md](PRESENTATION_SCRIPT.md) | Spoken script, 5–10 minutes, with demo stage directions. |
| [QA_PANEL.md](QA_PANEL.md) | Anticipated panel questions and answers from the actual code, schemas, and registry. |
| [EDIT_POINTERS.md](EDIT_POINTERS.md) | Where to change the live app vs the ML factory after the evaluation. |

## How to present

1. Open `SLIDES.html` full screen. Core path if time is tight: **1–4, 11–20, 24–26** (title, two systems, pipeline, GI-001/002, numbers, fail, close).
2. Keep `PRESENTATION_SCRIPT.md` on a second screen or printed.
3. Demo only `http://localhost:5173` with backend **8010**. Do not open root `frontend/` or port 8000.
4. If they go deep, jump to `QA_PANEL.md` categories A–E. Do not improvise a promotion.

## One-line truth

Live writer = Qwen2.5-3B GGUF. Candidate `qwen25-lora-20260815-090709` = **FAIL** (LLM-judge 0.557 / 0.621). Not promoted.
