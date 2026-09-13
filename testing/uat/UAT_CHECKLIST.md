# User acceptance testing — student journeys

Run these on a **running** stack. Automated tests in this folder skip unless `LEARNMATE_UAT=1`.

## Start the product (ports that this project actually uses)

```bash
cd integrated-backend
docker compose up -d
# .env must contain JWT_SECRET_KEY
uvicorn server:app --reload --port 8010

cd ../integrated-frontend
# .env: VITE_API_BASE_URL=http://localhost:8010
npm run dev
```

Open `http://localhost:5173`. Do **not** use root `frontend/` or API port **8000**.

---

## Journeys

Tick the box only if the behaviour is visible on screen (or the gap is recorded in Notes).

### A-01 Public explore
- [ ] `/` shows Home without forcing login
- [ ] `/about` and `/tour` work signed out
- [ ] Unknown URL lands on Home, not a blank login wall

**Notes:**

### A-02 Register and login
- [ ] Register with name, valid email, password ≥8 chars with a number → lands in the app
- [ ] Weak password is explained (needs length / a number)
- [ ] Duplicate email is rejected
- [ ] Login with wrong password says only “Invalid email or password”
- [ ] Refresh keeps the session (`/api/auth/me`)

**Notes:**

### A-03 Upload
- [ ] PDF appears immediately as Processing, then Ready
- [ ] Non-PDF is rejected in the browser (“Only PDF files are accepted”)
- [ ] File over 10 MB is rejected before upload
- [ ] Password-protected PDF returns a readable 400
- [ ] Scanned PDF with no text: honest error, no OCR

**Notes:**

### A-04 Generate study resources
- [ ] Key points (passage) shows job progress text, not a silent spinner
- [ ] Resource opens after the job completes
- [ ] **Known gap:** judge `score` / `accepted` / `reasoning` may be missing on ResourceView even when the API returns them — record, do not invent the UI

**Notes:**

### A-05 / A-06 Chat
- [ ] Question the PDF clearly answers produces a reply
- [ ] Follow-up that uses “it” / “this” still makes sense (rewrite node)
- [ ] **Known gap:** chat bubble may not show pdf vs general badge; API still has `turn.mode`

**Notes:**

### A-07 Auth edge
- [ ] Logged-out visit to `/documents` redirects to `/login`
- [ ] After token expiry, next API call sends the user to login

**Notes:**

### A-08 Health
- [ ] `GET http://localhost:8010/api/health` returns JSON
- [ ] `status` is `ok` only if Mongo **and** vectors are up
- [ ] Mongo URI shows port **27018**, Qdrant **6335**

**Notes:**

### A-09 Analytics / account
- [ ] Analytics page loads for a user with history (or empty state)
- [ ] Account settings page opens (prefs may not persist — known gap)

**Notes:**

### A-10 Sign-off
- [ ] Tester name: _______________
- [ ] Date: _______________
- [ ] Environment (CPU/GPU, first-load of GGUFs?): _______________
- [ ] Result: Pass / Pass with known gaps / Fail

---

## Optional automated smoke (live models, slow)

From `integrated-backend`:

```bash
python scripts/smoke_test.py path\to\small.pdf --base-url http://localhost:8010
```

If the script has no `--base-url` flag yet, it still defaults to **8000** — that is a product bug. Prefer the pytest UAT module which reads `LEARNMATE_API_URL`.
