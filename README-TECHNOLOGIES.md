# LearnMateAI — technologies used

Every technology, library and model in the project, with a plain-English reason for each.

Nothing here is a cloud service. The whole system — including the language models — runs on
one machine, and no uploaded document ever leaves it.

**At a glance**

| Layer | Choice |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS 4, React Router 7, Axios |
| Backend | Python 3.13, FastAPI, Uvicorn |
| AI orchestration | LangChain Core 1.x, LangGraph 1.x |
| Language models | Qwen2.5-3B (writes), Llama-3.2-3B (grades) — local, via llama.cpp |
| Search | sentence-transformers embeddings + a cross-encoder reranker |
| Databases | MongoDB 8, Qdrant 1.18 (both in Docker) |
| Security | PyJWT, bcrypt |

---

## 1. Frontend

| Technology | Version | Why it is used |
|---|---|---|
| **React** | 19.2 | Builds the interface out of reusable components. The screen changes constantly here — a reply arriving word by word, a document turning from Processing to Ready — and React redraws only the part that changed. |
| **Vite** | 8.2 | The build tool and development server. Saves show up in the browser instantly, and it produces one small optimised bundle for release. |
| **React Router** | 7.18 | Gives each page its own web address, so `/chat` and `/documents` can be bookmarked, shared and reloaded. Also enforces which pages need a login. |
| **Tailwind CSS** | 4.3 | Styling written directly on the element instead of in separate stylesheets. Keeps every page visually consistent without a growing pile of CSS files nobody dares delete. |
| **Axios** | 1.19 | Talks to the backend. Chosen over the browser's built-in `fetch` for one feature: interceptors. The login token is attached to every request automatically, and an expired session is caught in one place instead of in forty. |
| **ESLint** | 10.8 | Catches mistakes — unused variables, misused React hooks — before they reach the browser. |

---

## 2. Backend — the web layer

| Technology | Version | Why it is used |
|---|---|---|
| **FastAPI** | 0.115+ | The web framework. Chosen because it validates every incoming request against a declared shape, so bad input is rejected with a clear message rather than crashing somewhere deeper. It also generates live API documentation at `/docs` for free. |
| **Uvicorn** | 0.30+ | The server that actually runs FastAPI and handles the network connections. |
| **Pydantic** | (with FastAPI) | Defines what a valid request looks like. If a field is missing or the wrong type, the request never reaches our code. |
| **PyJWT** | 2.8 | Issues and checks login tokens. After signing in, the browser holds a signed token instead of the server keeping a session — which means the server stays stateless and can be restarted without logging everyone out. |
| **bcrypt** | 4.1 | Hashes passwords. Deliberately slow, which is exactly what you want: it makes guessing passwords in bulk impractical even if the database is stolen. Passwords are never stored or logged in readable form. |
| **python-multipart** | 0.0.9 | Handles file uploads. FastAPI cannot accept an uploaded PDF without it. |
| **email-validator** | 2.1 | Checks that a registration email is really an email address. |
| **python-dotenv** | 1.0 | Reads settings from a `.env` file, so passwords and model paths are configuration rather than code. |

---

## 3. The AI engine

| Technology | Version | Why it is used |
|---|---|---|
| **langchain-core** | 1.5 | The common vocabulary for talking to language models — messages, prompts, streaming, and the `BaseChatModel` interface our local-model wrapper implements. Because our code speaks this interface, swapping the local model for a served one or a cloud API is a configuration change instead of a rewrite. |
| **langchain-text-splitters** | 1.1 | Cuts a document into overlapping chunks, breaking at sentence and paragraph boundaries rather than mid-word, so a chunk is still readable on its own. |
| **LangGraph** | 1.2 | Runs the two agents as **state machines** rather than one long function. A chat turn is `rewrite → retrieve → generate → evaluate → decide`, where `decide` either accepts the answer or sends it back to be rewritten. Loops like that are awkward to write by hand and are what this library exists for. |
| **langchain**, **langchain-community** | 1.3, 0.4 | Listed in `requirements.txt` for compatibility with the LangChain family, but **not imported anywhere in this codebase** — the project uses `langchain-core`, `langchain-text-splitters` and `langgraph` directly. Noted here rather than left to be discovered. |
| **llama-cpp-python** | 0.3 | Runs the language models **on this machine** — no API key, no internet, no data leaving the computer. It also supports *grammar-constrained decoding*, which is the important part: the model is forced to produce valid JSON. Without it, a 3B model asked politely for JSON returns prose about half the time. |
| **sentence-transformers** | 5.0 | Turns text into vectors (lists of numbers) so passages can be found by meaning rather than by exact words. Runs both the search model and the reranker. |
| **PyTorch** | 2.6 | The numerical engine underneath sentence-transformers. Not used directly. |
| **transformers** | 5.0 | Model loading and tokenisation, used by sentence-transformers. Not used directly. |
| **PyMuPDF** | 1.26 | Reads PDFs — page text, page count, and whether a file is encrypted or corrupt. One library for extraction, cleaning and upload validation, so a PDF behaves the same at every step. |
| **NumPy** | 2.0 | Vector arithmetic, used when comparing embeddings. |
| **huggingface_hub** | 0.20 | Downloads the models on first run, so a fresh install needs no manual file copying. |
| **google-genai** | 1.0 | **Optional and unused by default.** Only loaded if the project is pointed at Google's Gemini API instead of the local models. Safe to uninstall for a fully offline setup. |

### The models themselves

| Model | Size | Job |
|---|---|---|
| **Qwen2.5-3B-Instruct** (Q4) | ~2 GB | The **generator** — writes chat replies and study material. |
| **Llama-3.2-3B-Instruct** (Q4) | ~2 GB | The **judge** — grades what the generator wrote and says what to fix. |
| **all-MiniLM-L6-v2** | ~90 MB | Turns document chunks and questions into vectors for searching. |
| **ms-marco-MiniLM-L-6-v2** | ~90 MB | Re-reads the top search results *together with* the question and reorders them properly. |

Laptop-sized substitutes for each row (Gemma 2 2B / Phi-3.5 Mini generators, Gemma or Granite judges, BGE-small or E5-small embedders, MiniLM-L-12 or BGE reranker, plus ANN vs hybrid retrieve) are researched and scored on branch `thevindu-models`. They are **not** live defaults. Runbooks live in `thevindu-models/`; numbers in `thevindu-models/RESULTS.md`.

Two deliberate choices worth explaining to a reader:

- **The judge is a different model family from the generator.** A model grading its own writing rates its own style highly, and the quality check stops catching anything. Different weights means a genuine second opinion.
- **"Q4" means quantised.** The models are compressed from 16 bits per number to about 4, which makes them roughly a quarter of the size and fast enough to run on an ordinary laptop, for a small loss in quality.

---

## 4. Databases

| Technology | Version | Why it is used |
|---|---|---|
| **MongoDB** | 8 | Stores everything that is not a vector: accounts, documents, page text, chat history, generated material, the evaluation log, the job queue. Chosen because the records have genuinely different shapes — an MCQ, a summary and a chat turn are not the same thing — and a document database stores them without inventing a table for each. |
| **GridFS** | (part of MongoDB) | Stores the original PDF files inside MongoDB, so the uploaded file and its extracted text cannot be separated by a stray file deletion. |
| **PyMongo** | 4.9 | The Python driver for MongoDB. |
| **Qdrant** | 1.18 | A purpose-built **vector database**. It holds the embeddings of every document chunk and answers "which passages are closest in meaning to this question" in milliseconds, using a proper index rather than comparing against every chunk one at a time. |
| **qdrant-client** | 1.15 | The Python driver for Qdrant. Kept within one minor version of the server, which is as far apart as it tolerates. |
| **dnspython** | 2.7 | Only needed if MongoDB is moved to a hosted cluster (`mongodb+srv://` addresses). Harmless locally. |
| **Docker Compose** | — | Runs both databases as containers with one command, each with its own storage volume, so no manual database installation is required and neither can be wiped by another project on the same machine. |

---

## 5. Development and testing

| Technology | Why it is used |
|---|---|
| **Git** | Version control. |
| **Python 3.13** | The version this project was developed and verified on. |
| **Python venv** | Keeps this project's Python packages separate from everything else on the machine. |
| **requests** | Used only by `scripts/smoke_test.py`, which drives the whole system end to end — register, upload, generate, chat, read analytics — and prints a pass or fail line per step. |
| **`/api/health`** | A built-in endpoint that reports both databases and both model files separately, so a problem can be located in seconds rather than guessed at. |

---

