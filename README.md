# LearnMateAI

AI-powered study platform for Sri Lankan legal education. Upload a PDF, ask grounded
questions, and generate study resources. A second model grades what the first wrote.
===
This file is an index. The project docs were split on `main`; the offline fine-tuning
track lives in `model-Thevindu/`.

| Document | Covers |
|---|---|
| [README-APPLICATION.md](README-APPLICATION.md) | How the software is put together |
| [README-USAGE.md](README-USAGE.md) | Running it, and using it as a student |
| [README-TECHNOLOGIES.md](README-TECHNOLOGIES.md) | Libraries and models, with reasons |
| [README-MACHINE-LEARNING.md](README-MACHINE-LEARNING.md) | Live retrieval / judge, and the offline LoRA track |
| [model-Thevindu/README.md](model-Thevindu/README.md) | Fine-tuning folder layout and honesty board |
| [integrated-backend/README.md](integrated-backend/README.md) | Backend layout, config, endpoints |
| [integrated-frontend/README.md](integrated-frontend/README.md) | React app |

**Live path today:** `integrated-frontend` + `integrated-backend` (local Qwen 2.5 + Llama 3.2 via llama.cpp).  
**Offline path:** `model-Thevindu/` — corpus → pairs → LoRA → eval → promote a pointer. The first real candidate (`qwen25-lora-20260815-090709`) **failed the gate**. Do not promote it. The app must keep its generator / API fallback.

Semester 5 group project. Contributions land on feature branches and pull requests into `main`.
