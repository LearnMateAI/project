# LearnMateAI — running and using it

Two parts: getting it running on a machine, and what to do with it once it is.

For how the software is put together see `README-APPLICATION.md`; for the models and how
their output is judged see `README-MACHINE-LEARNING.md`.

---

# Part 1 — Running it

## What you need

| | |
|---|---|
| Python | 3.13 (what it was developed and verified on) |
| Node | 18+ |
| Docker | for MongoDB and Qdrant |
| Disk | ~4 GB for the two models, plus your PDFs |
| RAM | 8 GB works; 16 GB is comfortable |

No API keys and no internet connection are needed once the models are downloaded. Nothing
you upload leaves the machine.

## First run

```bash
# 1. databases — MongoDB on 27018, Qdrant on 6335, each with its own volume
cd integrated-backend
docker compose up -d

# 2. python dependencies
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt        # Windows
# source venv/bin/activate && pip install -r requirements.txt    # macOS/Linux/git bash

# 3. settings
copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
#   paste the output into JWT_SECRET_KEY — it is the only setting with no default

# 4. run the Backend
python -m uvicorn server:app --reload --port 8010
```

```bash
# 5. the frontend, in a second terminal
cd integrated-frontend
npm install
npm run dev
```

Open <http://localhost:5173>. 

The models are ~4 GB and download on first use. 

## Checking it end to end

```bash
Use the Frontend UI : Open <http://localhost:5173>. 
```


## Moving it to a machine with a GPU

The models run on the CPU by default, which is why a reply takes tens of seconds. On a GPU Server, offloading can make faster. 

In `integrated-backend/.env`:

```ini
LEARNMATE_N_GPU_LAYERS=-1        # all layers on the GPU. This is the line that matters.
LEARNMATE_N_THREADS=<P-CORES>    # sysctl -n hw.perflevel0.physicalcpu
LEARNMATE_N_THREADS_BATCH=<P-CORES>
LEARNMATE_N_BATCH=512
LEARNMATE_FLASH_ATTN=1
LEARNMATE_USE_MLOCK=1
API_WARM_MODELS=1                # load both models at boot, not inside the first question
```

`llama-cpp-python` must be built for Metal, or `N_GPU_LAYERS` does nothing:

```bash
CMAKE_ARGS="-DGGML_METAL=on" pip install --force-reinstall --no-cache-dir llama-cpp-python
```

Two things are gitignored and have to be copied by hand: `integrated-backend/models/` (the two GGUFs) and `.env` itself. 


---

# Part 2 — Using it

## The idea

A conversation and a set of study materials are always **about one PDF**. You upload a document, the system reads it, and everything after that is grounded to it.

## 1. Make an account

Sign up at <http://localhost:5173/register>. Accounts are local to this installation. Before signing up you can read **Home**, **About** and **Take a Tour** without an account.

## 2. Upload a document

**Documents**, then drop a PDF on the upload panel and pick a subject.

The row appears immediately as **Processing** and becomes **Ready** on its own — the page watches it, so there is nothing to refresh. Behind that: the text is extracted, cleaned (running heads stripped, ligatures repaired, hyphenation rejoined), split into overlapping chunks, and embedded into the vector index.



Limits: PDF only, 10 MB, 300 pages. Uploading a file somebody else already uploaded is very fast, because documents are stored by content hash and embedded once.

## 3. Ask it questions

**Chat**, then choose a document to start a conversation.


- **A question the document does not cover is answered from general knowledge instead.** It is a different kind of answer and it carries no page citations.
- **Conversations survive.** History is stored, so you can close the tab and pick up a conversation later.

## 4. Generate study material

Open a document in **Documents** and use the panel beside it. Four kinds:

| | |
|---|---|
| **Summary** | the passage in a few sentences |
| **Key points** | the points the passage treats as important |
| **MCQs** | four options, one right, three plausible |
| **Practice questions** | short-answer, with answers |

Two scopes for generation:

- **Passage** — one extract, optionally the pages best matching a topic you name. 
- **Whole document** — read in groups and pooled. 

Generation runs in the background. **Resources** lists what is still running above what is finished, with live progress, so you can leave the page and come back.

Every generation is checked before you see it: structural checks first (an MCQ really has four options and exactly one marked answer), then a second model grades it against the
source passage. A rejected attempt is regenerated once with the judge LLM's instruction, and the better of the two attempts is what you get.

## 5. Track it

**Analytics** shows what you have generated and your activity over the last seven days.

---

