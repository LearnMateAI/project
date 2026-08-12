# LearnMateAI — integrated frontend

The React app for [`integrated-backend/`](../integrated-backend). Upload a PDF, chat with it,
generate study material from it, and see how well any of that scored.

Built from `frontend/` — Tharumini's app — with the same stack, the same look and most of
her pages carried over. What changed is everything downstream of the backend merge, which
is covered under [What changed from `frontend/`](#what-changed-from-frontend).

---

## Quickstart

The backend has to be running first:

```bash
cd integrated-backend
docker compose up -d
venv\Scripts\python -m uvicorn server:app --reload --port 8010
```

Then:

```bash
cd integrated-frontend
npm install
copy .env.example .env      # already points at http://localhost:8010
npm run dev
```

Open <http://localhost:5173>, register an account, and upload a PDF from the dashboard.

**Port 8010, not 8000.** Port 8000 on this machine is answered by an unrelated
`simplytask-backend` container; uvicorn binds `127.0.0.1:8000` without complaining but every
request goes to the container, so the API appears to 404 on every route. If you move the
backend, change `VITE_API_BASE_URL` in `.env` to match.

If Vite starts on a port other than 5173 (it will, if 5173 is busy), add that origin to
`FRONTEND_ORIGIN` in `integrated-backend/.env` — it takes a comma-separated list — or CORS
will block every request.

---

## How it is put together

```
src/
├── api/          one module per area, all on the shared axios client
├── context/      who is logged in
├── hooks/        useJob — the one that matters
├── components/   layout, and the pieces shared across pages
└── pages/        one file per screen
```

Everything lives under `src/`. In `frontend/` the `pages/` and `api/` folders sat at the
repo root beside `src/`, which is why its imports read `../src/context/useAuth.js` and
`../../api/routes.jsx`; here they are `../context/useAuth.js` and `../api/client.js`.

### Long work runs as a job, and that shapes three screens

Uploading, generating and chatting all return **`202 {job_id}`** instead of a result,
because a 3B model on a CPU takes 30 seconds to several minutes and no browser will hold a
connection that long. So every one of those calls is really two steps:

```js
const job = useJob();
await job.run(() => generateResource({ documentId, resourceType: "mcq", scope: "document" }));
// job.progress.message  →  "Group 2/5: Generating mcq (attempt 1/2)..."
// job.result            →  the finished resource
```

[`src/hooks/useJob.js`](src/hooks/useJob.js) wraps
[`waitForJob`](src/api/jobs.js), which polls `GET /api/jobs/{id}` every 1.5 s. It aborts on
unmount, so navigating away mid-generation stops the polling rather than setting state on a
tree that no longer exists.

The progress text comes from the backend, which writes real commentary onto the job record —
*"Summarising page 4 (4/7)…"*, *"Structural check passed. Judging…"*. During a five-minute
run that is the difference between the app looking busy and looking hung, which is why
[`JobProgress`](src/components/JobProgress.jsx) shows the message rather than a spinner.

### Two things the UI has to say that the text cannot

**Which mode answered.** A chat reply written from the document and one written from the
model's general knowledge read identically. The backend decides between them by retrieval
score and reports it, so [`ModeBadge`](src/components/ModeBadge.jsx) puts *From your
document* or *General knowledge* on every reply, with the cited pages and the retrieved
text behind a disclosure. Reading a general-knowledge answer believing it came from your
lecture notes is exactly the mistake this project exists to prevent.

**Whether the evaluator passed it.** Everything generated is graded by a second model, and
content that scored below the threshold is stored and shown anyway, flagged.
[`QualityBadge`](src/components/QualityBadge.jsx) always says which of *reviewed*,
*flagged* or *not reviewed* applies. Hiding rejections would make the failure rate
invisible, and the analytics page exists partly to make it visible.

### Resources are addressed by id

One route, `/resources/:resourceId`, fetches the resource and picks a renderer from its
`resource_type` — prose, a bulleted list, an interactive quiz, or questions with answers on
demand. `frontend/` passed the object through router state, which cannot survive a refresh
and cannot be linked; a student will want to come back to a quiz.

---

## Screens

| | |
|---|---|
| **Dashboard** | upload, recent resources, headline counts |
| **Documents** | library, PDF viewer, and the generation panel. Re-polls while anything is `Processing`, so a row becomes `Ready` on its own |
| **Resources** | everything generated, filterable by document and type |
| **Resource** | one resource — quizzes are interactive, answers hidden until you submit |
| **Chat** | conversations, one per document, with mode/score/pages on every reply |
| **Analytics** | activity counts, plus the judge's score distribution and which gate decided each attempt |

### The `scope` choice, and why the panel explains it

Generation takes **scope**, and it is not a speed setting:

- **One passage** — a single extract, or the pages that best match a topic. Seconds. This
  is *"five questions about directors' duties"*.
- **The whole document** — read in groups and pooled. Minutes, and the only way to get a set
  that is about the whole PDF.

Asking for forty questions at passage scope does not fail. It quietly returns forty
questions about the opening six thousand characters, which is why the form spells the
difference out instead of offering a two-word dropdown.

---

## What changed from `frontend/`

**Carried over almost unchanged:** the auth context, `ProtectedRoute`, `Layout`, `Sidebar`,
`Topbar`, login, register, and the summary and key-points renderers. Same Tailwind
vocabulary throughout — white cards, grey background, blue accent — so the new screens sit
beside the old ones without a seam.

**Changed because the backend did:**

1. Upload and generate return `202 {job_id}`; both now poll.
2. `verification_status: "Unverified"` is gone — `accepted`, `score`, `threshold` and
   `n_attempts` replace it.
3. The three buttons disabled as *"Coming Day 10"* are real: MCQs, practice questions, and
   both scopes for all four types.
4. Chat and analytics are built; they were one-paragraph placeholders.

**Fixed on the way through:**

- The documents table had its **Status and Chunks columns swapped** against its headers.
- The upload size check allowed **50 MB** where the server accepts **10 MB**, so oversized
  files uploaded fully and were then rejected.
- The login form printed **hardcoded demo credentials** (`alice@example.com` / `alice@123`).
- **A 401 anywhere** now clears the session and returns you to the login page; an expired
  token used to surface as an unrelated error on whichever page made the next call.
- A stored token is **validated against `/api/auth/me`** on startup rather than trusted.

**Dropped:** `server.js`, `app.jsx` and `main.jsx` (all three empty), and `src/App.css`
(unused Vite starter styles).

---

## Troubleshooting

**Every request fails with a CORS error.** The dev server is on a port
`integrated-backend/.env` does not list. Add it to `FRONTEND_ORIGIN` and restart the backend.

**"Cannot reach the server."** The backend is not running, or `VITE_API_BASE_URL` points at
the wrong port. Check <http://localhost:8010/api/health> directly. Vite only reads `.env` at
startup, so restart `npm run dev` after changing it.

**A generation has been running for minutes.** That is normal on the local models — watch
`progress.message`. Turning off *Review before showing* roughly halves it. Whole-document
runs on a long PDF are genuinely several minutes.

**A resource came back with fewer items than I asked for.** The panel says so when it
happens. The backend never pads a short set: the document did not support more, or the
duplicates two page-groups both produced were dropped.

**Everything logged me out.** The token lasts 24 hours by default
(`JWT_EXPIRY_HOURS` in the backend's `.env`).

---

## Scripts

| | |
|---|---|
| `npm run dev` | dev server on 5173 |
| `npm run build` | production build into `dist/` |
| `npm run preview` | serve that build |
| `npm run lint` | eslint |
