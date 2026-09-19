# Last recorded pytest results

Branch: `testing` only. Command run from the repository root.

| Date | Command | Passed | Failed | Skipped | Notes |
|------|---------|--------|--------|---------|-------|
| 2026-08-19 | `python -m pytest testing/unit testing/integration testing/uat --tb=line` | **97** | 0 | **4** | Skips are live UAT (`LEARNMATE_UAT` unset). No GGUF load. |

## Layer breakdown

| Layer | Result |
|-------|--------|
| Unit (`testing/unit`) | all passed |
| Integration (`testing/integration`) | all passed |
| UAT (`testing/uat`) | 4 skipped until `LEARNMATE_UAT=1` and API `:8010` |

## How to re-run

```bash
pip install -r testing/requirements.txt
python -m pytest testing/unit testing/integration testing/uat -q
```

## 2026-09-19 — frontend R-03/R-06 interim result on `deployment`

| Item | Command / scope | Passed | Failed | Pending / note |
|------|-----------------|-------:|-------:|----------------|
| R-03 component cases | `npm test -- --run tests/components.test.jsx` | 27 | 0 | Reader, static keypoints, chat, citations, upload and existing components. |
| R-06 targeted checks | `npm test -- --run tests/branch-regressions.test.jsx` | 5 | 0 | Run on deployment code (same commit as local `tharumini-dev`); branch-isolated full suites pending. |
| All frontend Vitest | `npm run test:report` | 46 | 1 | Existing stale-token auth regression remains failing; JUnit and coverage in `test-reports/`. |
| Cypress / live UAT | Not rerun in this entry | 0 | 0 | Live Vite/FastAPI/Keycloak available; old Cypress report is 1 pass / 3 pending. |

Known gaps / test-plan deviations: `DocumentReader` loads all extracted pages at once, without pagination; `Flashcards` is a static numbered list, without flip interaction; document deep links use `/documents?open=<id>`, not `/documents/:id`. The removed ModeBadge/QualityBadge pair is represented by citations and a flagged warning, and uploads accept PDF/DOCX/PPTX/TEX rather than PDF-only. R-03 tests follow these existing behaviors. The reader shows a generic readable error for 404, not an explicit not-found message. Chat-session rename and whitespace-title rejection are absent; Journey B will test resume and delete instead. A further R-13 mismatch: `exportResource` exists in the API module but is unused by the UI, so the requested DOCX/PPTX export click cannot run as written. The dedicated `learnmate-e2e` Keycloak client and disposable User B were provisioned idempotently; both users' tokens were accepted by FastAPI. See `test-reports/SUMMARY.md` for counts, coverage, and the auth failure.

## 2026-09-19 — Bug fixes (both confirmed bugs from this pass)

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | Bug 1 fix: stale-session clearing | Claude | 1 | 1 | 0 | 0 | 100% | `src/context/AuthProvider.jsx`: the `check-sso` resolution effect only stored token/user on success; when `initKeycloak` resolved `false` or rejected (expired/invalid stored token), the existing `token`/`user` state and `localStorage` entries were left in place, so `ProtectedRoute.jsx` (which only checks token presence) kept rendering protected views. Fixed by explicitly clearing `localStorage` ("token", "user") and resetting `token`/`user` state to `null` in both the not-authenticated branch and the `catch` block. Regression test `tests/auth.test.jsx` ("redirects when a stored token is expired and check-sso rejects it") now passes and additionally asserts localStorage is cleared. |
| 2026-09-19 | Bug 2 fix: Cypress baseUrl/CORS host mismatch | Claude | 1 | 1 | 0 | 0 | 100% | `cypress.config.js`: default `baseUrl` changed from `http://127.0.0.1:5173` to `http://localhost:5173` so Cypress runs against the host `FRONTEND_ORIGIN` (`http://localhost:5173` in `integrated-backend/.env`) actually allows for CORS; previously a 127.0.0.1-origin run got 400s on API preflight past login. This is a test-config fix only, not a backend change. Noted, not fixed: Keycloak's client still registers both `localhost` and `127.0.0.1` redirect URIs while the backend only allows `localhost` for CORS — that disagreement should be resolved deliberately by the team, not patched unilaterally in backend config. |
| 2026-09-19 | Full frontend Vitest (post-fix) | Claude | `npm run test:report` | 47 | 0 | 0 | 100% | All 7 suites green (up from 46/1). Coverage: 43.31% statements, 35.17% branches, 35.35% functions, 44.69% lines. JUnit: `test-reports/vitest-junit.xml`. |

## 2026-09-19 — R-13 Cypress: first live run of `cypress/e2e/pipeline.cy.js`

This spec (real-hosted-login test, Journeys A/B/C, corrupt-token, degraded-generation) was written
by an earlier session but had **never actually executed live** — it was gated behind `E2E_*` env
vars that were never set (old report: 1 pass / 3 pending, all `liveIt` tests skipped). This is the
first real run against the live stack, so failures below are genuine first-contact findings against
untested test code, not regressions.

**Real app bug found and fixed:** `src/components/WorkspaceChat.jsx`'s session-open effect had no
StrictMode/concurrency guard (unlike the equivalent effect in `src/pages/chat.jsx`, which already
used the correct pattern). Opening a document's embedded chat panel could create two chat sessions
for the same document — confirmed via direct API calls (two `session_id`s, same `document_id`,
timestamps 3ms apart; one held the real conversation, the other was an empty orphan). Fixed by
converting the effect to a single async function with a `cancelled` flag checked *before* the
create-or-reuse decision (not just before the final `setState`), mirroring `AuthProvider.jsx`'s
existing idiom. Confirmed via the chat-sessions API that only one session now exists after
re-running the affected journey.

**Design change (user-approved):** `loginFast()` originally minted a token via a direct grant
against the dedicated `learnmate-e2e` client and injected it into `localStorage`, without ever
establishing a real Keycloak SSO cookie. Today's Bug 1 fix makes `AuthProvider` clear any session
`check-sso` can't verify — and `check-sso` runs on every full-page load regardless of what's
sitting in `localStorage`, so it immediately wiped this injected token on the next navigation.
Per user's direction, `loginFast`/`hostedLogin` now perform the actual hosted Keycloak login (same
`cy.origin()` mechanism as the one real-login test), cached via `cy.session` so repeat calls are
fast in practice. No production code changed for this; `learnmate-e2e` remains provisioned for any
future direct-API testing that doesn't go through the browser session.

**Test-only bugs found and fixed (pipeline.cy.js):**
- Hosted-login session setup asserted on `location.pathname === "/dashboard"`, but Keycloak's
  redirect lands there as a hard navigation *before* `AuthProvider` finishes exchanging the code —
  the URL reads `/dashboard` well before the token is actually written to `localStorage`. Fixed to
  also wait for real dashboard content before treating the session as established.
- `cy.contains("button", "Ask")` is a substring match and also matched the still-rendered
  "Ask the record" tab button, so it silently re-clicked the tab instead of submitting the
  question. Fixed to match exact text (`/^Ask$/`).
- `.type()` into the embedded chat input does not itself retry when the target is disabled (it
  fails immediately rather than waiting) — WorkspaceChat disables that input until its own
  session-open call resolves. Fixed with an explicit `.should("not.be.disabled")` on its own
  `cy.get()`, followed by a second, separate `cy.get()` for the `.type()` (chaining `.should()`
  straight into `.type()` can hand it a stale element reference from just before a re-render).
- The library page's document switcher is a native `<select>` whose `<option>`s carry each
  filename; a collapsed `<option>` is never "visible" per the browser, so `cy.contains(filename)`
  could match that hidden option instead of the reader's own `<h2>`. Fixed by scoping to `h2` for
  reader-open assertions.
- Journey C assumed a second user, opening another owner's document via `?open=<id>`, would fall
  back to showing one of their own documents. Actual behavior (`src/pages/documents.jsx`): the
  `open` effect only auto-selects an id found in *that user's own* document list; for anyone
  else's id it matches nothing and selects nothing, with no fallback. Fixed the assertion to check
  the user's own document appears as a library tile, not that it opens in the reader.
- "Degraded resource generation" assumed the resource-type dropdown defaults to "Summary"; actual
  default (`src/components/ResourcesPanel.jsx`) is "keypoints", so the submit button read
  "Generate Key points". Fixed by explicitly selecting "summary" before generating.
- "Corrupt stored token" directly overwrote `localStorage.token`, but since every login is now a
  real one, `AuthProvider`'s own `check-sso` mount effect (not just its 20s background refresh)
  legitimately re-authenticates from the live SSO cookie and rewrites a fresh token shortly after
  mount — racing and undoing the corruption before the test's click fired. Fixed by waiting for
  the authenticated page to render first (proving check-sso's own write already happened) before
  corrupting the token. An earlier attempt at this fix used a persistent `cy.intercept` forcing
  every `/api/documents` call to 401, which caused a genuine infinite redirect loop (check-sso
  kept re-authenticating from the live cookie and retrying the poisoned endpoint) — reverted in
  favor of the localStorage approach, and the assertion now only checks that the app left
  `/documents` rather than that the token stays cleared forever (real SSO recovery afterward is
  correct behavior, not a bug).

**Confirmed passing after fixes:** the real hosted-login test, the Bug-1 session-expiry test,
Journey A (upload → cite → generate MCQ), Journey C (cross-user isolation), and "degraded resource
generation" all passed cleanly in a full-suite run.

**Journey B: FAILS, root cause confirmed — real backend write-after-read lag, not a frontend or
test bug.** Its reload step (resume conversation → send a follow-up → reload → expect both
messages still visible) consistently failed across five clean runs, each starting from verified-empty
prior state (leftover sessions explicitly deleted via the API before each attempt, so no run's
result could be a false positive from earlier debug data). Direct API checks after every failing
run confirmed the backend had genuinely persisted *all four* messages (both exchanges) correctly —
so this is not data loss. To find the actual cause, `cy.intercept` was used to record every
`GET /api/chat/sessions/{id}/messages` response during one full run: all four calls the frontend
made — two before the reload, two after (each pair doubled by React StrictMode's dev-mode
double-invoke) — returned exactly 2 messages, never 4, even though a manual API check moments after
the test ended showed 4. The reply is shown live in the chat UI straight from the send-message job's
own response, not from a fresh fetch of the message history; the actual write to that queryable
history evidently lands measurably later than the job response and the UI's citation-chip render
(which itself already comes from that same live response, so waiting on it — the fix attempted in
this pass — doesn't help). A `Cache-Control`/`Pragma: no-cache` header was also added to the axios
client as a first hypothesis (HTTP caching serving a stale reload response); the instrumented
capture proved this wasn't the cause (fresh calls, not cached ones, were returning the stale count),
so that change was reverted to keep the diff minimal. **This needs backend investigation** into how
long a sent message takes to become readable via `GET .../messages` after its job completes — out
of scope for this frontend Cypress pass to fix. No frontend or test code changes are pending on
this; the test's assertion (expect the follow-up visible within the default ~15s after reload)
accurately reflects a real, currently-unmet expectation and should stay as-is until the backend
timing is addressed, rather than being loosened to hide the gap.

## 2026-09-19 — R-13 Cypress journeys, per-item results

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | R-13 real hosted-login test | Claude | 1 | 1 | 0 | 0 | 100% | `cy.origin()` login against the real Keycloak form; passes cleanly after the Bug 2 baseUrl fix. |
| 2026-09-19 | R-13 Journey A (upload → cite → generate MCQ) | Claude | 1 | 1 | 0 | 0 | 100% | Passes cleanly after fixing an ambiguous `"Ask"` button selector and a disabled-input race in `WorkspaceChat`'s composer. |
| 2026-09-19 | R-13 Journey B (resume → follow-up → reload → delete) | Claude | 1 | 0 | 1 | 0 | 0% | FAILS on the reload step, confirmed real: backend write-after-read lag on `GET /api/chat/sessions/{id}/messages` (verified via instrumented network capture across 5 clean runs — see prose above). Not a frontend, caching, or test-flake issue. Needs backend investigation; not fixed in this pass. |
| 2026-09-19 | R-13 Journey C (cross-user document isolation) | Claude | 1 | 1 | 0 | 0 | 100% | Passes after correcting two wrong assumptions: a hidden `<select><option>` matching the reader's expected `<h2>`, and no fallback-selection behavior for another user's `open=<id>` deep link. |
| 2026-09-19 | R-13 session-expiry test (Bug 1 regression) | Claude | 1 | 1 | 0 | 0 | 100% | New test added this pass; forces an expired token, confirms redirect away from the dashboard and localStorage cleared. |
| 2026-09-19 | R-13 corrupt-token test | Claude | 1 | 1 | 0 | 0 | 100% | Passes after fixing a race against `AuthProvider`'s own real check-sso re-authentication (not the 20s background refresh as first suspected); an earlier `cy.intercept`-based fix attempt caused a genuine infinite redirect loop and was reverted. |
| 2026-09-19 | R-13 degraded resource generation | Claude | 1 | 1 | 0 | 0 | 100% | Passes after fixing a wrong assumption about the resource-type dropdown's default ("keypoints", not "summary"). |
| 2026-09-19 | Real bug fix: `WorkspaceChat.jsx` duplicate sessions | Claude | 1 | 1 | 0 | 0 | 100% | React StrictMode double-invoked the session-open effect with no concurrency guard, creating two chat sessions per document (confirmed via API: two `session_id`s, same `document_id`, 3ms apart). Fixed with the same `cancelled`-flag pattern already used in `AuthProvider.jsx` and `chat.jsx`. |

**R-13 summary: 6 of 7 items green; Journey B blocked on a real backend defect, not a test issue.**
The last full-suite run of all `liveIt` journeys together (all 6 fixed items green, Journey B
failing) reached 6 passing / 2 failing out of 8 total specs (the 2 failures were both Journey B
and its own precondition step at the time). `test-reports/cypress/mochawesome.html` on disk has
since been overwritten several more times by the narrower isolated runs below (Journey B
confirmation, then the R-12 cross-browser matrix) — it currently reflects only the *last* run
executed (the mobile-viewport Chrome pass under R-12), not a full-suite report. Treat the counts
in this file as authoritative over whatever a given moment's `mochawesome.html` happens to show.

## 2026-09-19 — R-02 live UAT (against the running stack)

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | UAT-11: multi-format upload | Claude | 4 | 4 | 0 | 0 | 100% | PDF (covered by R-13), DOCX, PPTX, and TEX all uploaded via `POST /api/documents` against the live backend, converted internally, and reached `processing_status: "Ready"` with correct page/chunk counts (DOCX: 1 page; PPTX: 3 pages; TEX: 2 pages). One thin single-slide PPTX first failed ingestion with "No substantive chunks produced" — retested with a 3-slide PPTX carrying real prose and it passed, confirming that was an under-filled test fixture, not a defect. Observation for the team (not a bug): the library always renames the stored/displayed filename to `<name>.pdf` and records `source_kind: "pdf"` even for DOCX/PPTX/TEX uploads, since everything is converted to a PDF representation internally — a user uploading `slides.pptx` will see `slides.pdf` in their library. |
| 2026-09-19 | UAT-11: disguised .exe rejected | Claude | 1 | 1 | 0 | 0 | 100% | A file with a real PE/MZ header saved as `malware_renamed.pdf` was rejected with 400 "This file is not a readable PDF." `learnmate/ingestion/formats.py::confirm_kind` does a magic-byte check specifically to catch this (`%PDF` for PDF, zip header for DOCX/PPTX) — already implemented, not a gap. |
| 2026-09-19 | UAT-16: generate summary, MCQ, key points | Claude | 3 | 3 | 0 | 0 | 100% | MCQ already existed from R-13 Journey A (8 accepted/flagged sets). Summary and key points generated fresh via `POST /api/resources/generate` against the live backend for the same document; both completed (`status: "done"`) with sensible content. Export validated via the API directly in R-08 below, not through the UI (no export button exists in this branch — known gap). |
| 2026-09-19 | UAT-19: citation accuracy on a multi-page source | Claude | 1 | 1 | 0 | 0 | 100% | R-13 Journey A already confirms this for a page-1 answer through the real UI. For a stronger check, a 3-page document was built (from the multi-slide PPTX above) and a question was asked whose answer only exists on page 3 ("What must the defendant's written answer contain under section 75?"). The reply correctly cited `page 3, paragraph 1`, matching the real source location — not just a coincidental page-1 default. |

All UAT-11/UAT-19 throwaway documents and sessions created for this pass were deleted afterward via
the API; they do not linger in `dev`'s library.

## 2026-09-19 — R-08 Postman/Newman against the REAL running API

New collection `integrated-frontend/tests/postman/learnmate-real-api.postman_collection.json` (37
requests, folders: Setup, Auth, Documents, Chat, Resources, Models) runs against the live
`http://localhost:8010`, not a mock — distinct from the existing
`tests/postman/learnmate.postman_collection.json` (5 flat requests against
`tests/postman/mock-api-server.mjs`, unfoldered, no negative cases). New npm script
`test:postman:real` (`node tests/postman/run-real-api.mjs`) runs it headless via Newman and writes
both an HTML (htmlextra) and a JUnit report to `test-reports/newman-real-api.html` /
`newman-real-api-junit.xml` — clearly separate filenames from the existing `newman-mock.html` so
the two are never confused.

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | R-08 real-API Newman collection | Claude | 37 assertions / 43 requests | 37 | 0 | 0 | 100% | First run found one real bug in the collection itself (not the API): the disposable test email used `@example.invalid`, which the backend's `email-validator`-backed `EmailStr` correctly rejects as a reserved/special-use domain (422) — swapped to `@example.com` and all 37 assertions passed. Covers real Keycloak RS256 tokens *and* the still-live local HS256 auth path (`/api/auth/register`, `/login`, `/me`), negative cases (no token, garbage token, wrong owner on documents/sessions/resources, bad page range via `first=0`, invalid export format), and DOCX/PPTX export (status 200, correct `Content-Type`, correct `Content-Disposition` extension, and a real ZIP/OOXML magic-byte check on the response bytes — not just a status-code check). |
| 2026-09-19 | R-08 diagnostic: messages-endpoint lag | Claude | 1 | 1 | 0 | 0 | 100% | New case added per today's Journey B finding: sends a chat message, polls the job to `status: "done"` (reading its own `finished_at` timestamp), then polls `GET /api/chat/sessions/{id}/messages` until the count reflects the new turn, reporting elapsed milliseconds directly in the test name so it shows in the Newman/JUnit/HTML report without digging through logs. Measured **658ms** and **1449ms** on two separate runs. This is a genuine, real, reproducible non-zero lag — but notably shorter than what alone would explain Journey B's Cypress failures (which timed out after 15s+, not ~1s). The concrete number is handed off as-is for backend investigation (per the instruction not to attempt a backend fix); the discrepancy between "lag exists" (confirmed twice, two different ways) and "how long the lag actually runs under Cypress's load" is not resolved and is worth Thevindu's own investigation rather than further guessing here. |

Also worth noting for the team: **documents** use a "not found" response for a non-owner (404,
existence hidden) while **chat sessions and resources** use "forbidden" (403, existence is
revealed) for an id that exists but isn't the caller's — both are deliberate, documented choices
in `app/services/ownership.py`, not a bug, but a real asymmetry the team should be intentionally
aware of rather than discover by accident.

## 2026-09-19 — R-12 cross-browser matrix

Only Google Chrome was installed on this machine. Per instruction, installed Microsoft Edge and
Firefox via Homebrew (`brew install --cask microsoft-edge firefox`) to complete the matrix. Ran
R-13 Journey A (upload → cite → generate MCQ) and Journey C (cross-user isolation) in each browser;
skipped Journey B per instruction, since it is blocked upstream on the confirmed backend defect
above. Added a mobile-width viewport pass (390×844, an iPhone-class width) in Chrome.

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | R-12 Chrome desktop (Journey A + C) | Claude | 2 | 2 | 0 | 0 | 100% | 17s total. |
| 2026-09-19 | R-12 Edge desktop (Journey A + C) | Claude | 2 | 2 | 0 | 0 | 100% | 19s total. Fresh Homebrew install needed one manual launch first (`open -a "Microsoft Edge"`) to clear a Gatekeeper quarantine flag on the newly downloaded app before Cypress could attach to it via CDP — a one-time environment step, not a product issue. |
| 2026-09-19 | R-12 Firefox desktop (Journey A + C) | Claude | 0 | 0 | 0 | 2 | N/A | **Not executed — environment limitation, not a product defect.** Cypress could not establish its automation connection to Firefox in this sandboxed macOS environment ("The browser never connected"), tried three ways: stock Firefox 156 (stable channel) headless, Firefox ESR 140 headless, and Firefox ESR 140 headed — all failed identically after the same connection-retry sequence. Chrome and Edge (both Chromium-based, using CDP) work fine; Firefox uses a different automation protocol (Marionette) that appears to be blocked or unreachable in this specific sandbox. This needs a non-sandboxed machine or CI runner to actually execute, not further local troubleshooting. |
| 2026-09-19 | R-12 mobile-width viewport, 390×844 (Journey A + C, Chrome) | Claude | 2 | 2 | 0 | 0 | 100% | 22s total. Same journeys, `--config viewportWidth=390,viewportHeight=844`. No layout-breaking failures at this width. |

**R-12 summary: 6/6 executed checks pass (Chrome desktop, Edge desktop, mobile viewport); Firefox
is a documented environment gap, not a failure to report as red.**

## 2026-09-19 — Five targeted fixes (1 real bug refinement, 4 hygiene)

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | Fix 1: AuthProvider catch-block refinement | Claude | 2 | 2 | 0 | 0 | 100% | `src/context/AuthProvider.jsx`: today's earlier Bug 1 fix cleared `localStorage` in *both* the resolved-false branch and the `catch` block; refined per instruction to only clear on a definite "no session" (resolved false), leaving the `catch` block (Keycloak genuinely unreachable) alone so a network blip doesn't log out a valid session. Added `tests/auth.test.jsx`: "keeps an existing session when check-sso is merely unreachable" (initKeycloak rejects, existing token/user untouched). Verified the existing "redirects when a stored token is expired..." test fails on a temporarily-reverted pre-fix copy of the file (dashboard renders instead of redirecting) and passes again once restored. |
| 2026-09-19 | Fix 2: Cypress baseUrl / hardcoded 127.0.0.1 | Claude | 1 | 1 | 0 | 0 | 100% | Already fixed as today's Bug 2. Grepped `cypress/` for hardcoded `cy.visit("http://127.0.0.1:5173...")` — none found; all visits already relative. Re-ran the hosted-login + Journey A specs live: 2/2 passing in 36s, no CORS error, Journey A reached upload/processing/MCQ generation. |
| 2026-09-19 | Fix 3: bandit B324 + B615 | Claude | 1 (bandit scan) | 1 | 0 | 0 | 100% | `learnmate/storage/qdrant_vectors.py`: added `usedforsecurity=False` to the non-cryptographic md5 hash used to bucket terms into a sparse vector index (B324). `learnmate/llm/download.py` + `registry.py` + `config.py`: the requested single hardcoded `revision=` would have been wrong for one of the two models `ensure_gguf` actually serves (Qwen and bartowski/Llama are different repos with different commit SHAs) — threaded `revision` through `_build`/`ensure_gguf` properly instead, with new `GENERATOR_REVISION`/`JUDGE_REVISION` config values (also documented in `.env.example`), pinned to each repo's actual current HEAD SHA fetched live from the HF API: Qwen `7dabda4d13d513e3e842b20f0d435c732f172cbe`, bartowski `5ab33fa94d1d04e903623ae72c95d1696f09f9e8`. `bandit -r integrated-backend/app integrated-backend/learnmate -ll`: 0 findings (was 2). |
| 2026-09-19 | Fix 4: jsx-a11y label associations | Claude | 1 (lint) | 1 | 0 | 0 | 100% | Added matching `htmlFor`/`id` pairs to the "Review before showing" checkbox in `ResourcesPanel.jsx` and the "Enable quality review by default" checkbox in `myaccountsettings.jsx`. Markup-only, no behavior change. |
| 2026-09-19 | Fix 5: stale testing/unit assertions | Claude | 97 (96 passed + 1 skipped) | 96 | 0 | 1 | 100%* | `test_frontend_contracts.py`: `test_auth_api_paths` now skips (not fails) since `src/api/auth.js` genuinely does not exist on this Keycloak-only branch — added `import pytest` + a guard; `test_upload_client_enforces_ten_megabytes` now matches the real error text. `test_pdf_validate.py`: both stale `match=` strings updated to the real current error messages (confirmed by reading `learnmate/ingestion/validate.py` directly before changing, not just applying the diff blind). `pytest testing/unit testing/integration -q`: 96 passed, 1 skipped, 0 failed (up from 93 passed / 4 failed). |

\* 1 skip, 0 fails is the correct outcome here, not a shortfall — `test_auth_api_paths` is designed to skip because the file it tests for no longer exists on this branch by design (Keycloak-only), not because something is broken.

**Regression check after all five fixes:** `npm run lint` — clean (0 errors, 0 warnings); this required also cleaning up an unused `useCallback` import and two stale/misplaced `eslint-disable` comments left over from today's earlier `WorkspaceChat.jsx` fix, which `npm run lint` caught. `npm test -- --run` — 48/48 passing (was 47; +1 for the new Fix 1 test).

## Scope Deviation — 19 Sep 2026

**Affects:** R-02 (Live UAT — UAT-12 "Rename a chat"), R-13 (Journey B, rename step)
**Status:** Dropped from this test cycle, not deferred as "untested"

Chat session rename is not implemented in the frontend. Searched the full
integrated-frontend/src tree for "rename"/"Rename" — no match. chat.jsx's session
sidebar supports only: start new chat, resume by clicking a session or by direct URL
(/chat/:sessionId), and delete. There is no rename control, no PATCH-style call to a
rename endpoint in api/, and no input affordance for it in the UI.

This is a missing feature, not a defect and not a test gap — there is nothing to
exercise. UAT-12 and the rename step of Journey B are removed from this cycle's scope
rather than logged as "failed" or "blocked."

**Disposition:** UAT-12 struck from the UAT checklist for this cycle. Journey B (R-13)
runs as: resume via URL -> reopen a past upload via ?open=<id> -> cross-user isolation
check. No rename step. If chat rename ships in a future build, re-add UAT-12 and extend
Journey B before the next test pass.

## R-06 — Unreviewed test code found in working tree, 19 Sep 2026

integrated-frontend/cypress/pipeline.cy.js was discovered untracked in the working
tree with no git history, no author, and no review trail, despite being actively used
and already responsible for finding and fixing six real bugs. It was also the source
of one claim (an "R-13 Journey C" cross-user repro) that turned out to rest on a
remembered terminal checkmark rather than any retained artifact — the claim was later
independently re-verified through direct API checks and a screenshot, but the
underlying test file's own assertions should not be treated as self-certifying
evidence until it has gone through the same review as production code.

**Action:** committed on branch `test/commit-pipeline-cy` for review (see STEP 2
above). Treat as in scope for R-06 (code with no test coverage or review of its own)
until merged and reviewed.

## 2026-09-19 — R-02 remaining UAT cases (Part 1) + model-dependent proof (Part 3)

Evidence for all items below: screenshots in
`integrated-frontend/cypress/screenshots/pipeline.cy.js/UAT*.png` (gitignored, not
committed — paths given for local reference), raw job JSON in `/tmp/uat18-results/*.json`
and `/tmp/uat-part3-*`, exported files in `/tmp/uat16-exports/`.

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | UAT-11: PDF/DOCX/PPTX/TEX upload, live UI | Claude | 4 | 4 | 0 | 0 | 100% | Fresh uploads (not reused from earlier passes) via the real UI: `UAT11-pdf-ready.png`, `UAT11-docx-ready.png` (green success banner: `"uat11-docx-check.docx" is ready: 1 extractable units, 1 passages.`), `UAT11-pptx-ready.png`, `UAT11-tex-ready.png`. All reached Ready. Note: the whole batch (4 uploads) completed in the same ~7s Cypress run — these are tiny fixture files and/or the ingest pipeline is fast enough on this hardware that no visibly-lingering "Processing" state was observed to screenshot; the badge simply read "Ready" by the time the UI re-rendered. Not a gap, just worth knowing the "Processing" screenshot the case description implies may not be catchable for files this small. |
| 2026-09-19 | UAT-11: disguised `.exe` renamed to `.pdf`, live UI | Claude | 1 | 1 | 0 | 0 | 100% | `UAT11-exe-rejected.png`: clear red banner "This file is not a readable PDF." — library count stayed at 4 filed/4 ready (not 5), confirming the file was never added, not silently accepted. |
| 2026-09-19 | UAT-15: multi-page continuous scroll (ADJUSTED) | Claude | 1 | 1 | 0 | 0 | 100% | No genuine multi-page PDF exists in this repo's fixtures — all 6 sample PDFs under `model-Thevindu/.../sample_pdfs/` are 1 page each (checked directly with PyMuPDF). Substituted the 3-slide PPTX from UAT-11 (renders as a 3-page document after conversion). First attempt screenshotted the default "PDF" tab and got a blank box — that tab is a raw `<iframe src={pdfUrl}>` (browser-native PDF rendering), which headless Chrome doesn't paint; not a bug, just the wrong tab to test. Recaptured on the "Text" tab (`DocumentReader`'s own rendering): `UAT15-multipage-fullscroll-TEXT-tab.png` clearly shows PAGE 1 / PAGE 2 / PAGE 3 stacked in one continuous scroll, in order, no pagination controls anywhere — confirms the case. |
| 2026-09-19 | UAT-15: out-of-range page API, direct | Claude | 3 | 3 | 0 | 0 | 100% | `GET .../pages?first=500&last=600` on a 3-page doc → `200`, `[]` (empty array, not a crash). `GET .../pages?first=3&last=1` (backwards range) → `200`, clamped to page 3 only (silent clamping, per `get_pages`'s `end = max(start, last or start)`). `GET .../pages?first=-5` → `422` with a structured validation message (Pydantic's `ge=1` constraint). **No 500 and no blank crash in any case — matches the ask — but the actual mechanism for a too-high-but-otherwise-valid range is silent clamping/empty-result, not an explicit "out of range" error.** Worth the team knowing that distinction if an explicit error was assumed. |
| 2026-09-19 | UAT-16: export at the API layer (BLOCKED at UI, scope note filed) | Claude | 6 | 6 | 0 | 0 | 100% | Generated summary + keypoints (reused from earlier R-02 pass) + MCQ (from R-13) on `sample_civil_procedure.pdf`. Exported all 3 × {docx, pptx} = 6 files directly via `GET /api/resources/{id}/export`. All 6: `200`, correct `Content-Type` (`.../wordprocessingml.document` or `.../presentationml.presentation`), clean descriptive filenames (`sample_civil_procedure_summary.docx`, etc. — not a generic name). Content verified by reading each file back with `python-docx`/`python-pptx` (the same library class the export code itself uses to write them) — summary reads as prose, keypoints as a numbered list, MCQ as questions/options/answer-key across slides, all matching the source resource's actual content. **Could not literally open these in Microsoft Word/PowerPoint** — neither is installed on this machine, and LibreOffice (`soffice`) is also not installed, so no native-app screenshot exists. The structural readback is the strongest verification available in this environment; flagging the gap rather than presenting a substitute as equivalent. |

**Scope note filed verbatim, UAT-16:** "UAT-16 tested at the API layer only — the export
endpoint works, but src/api/resources.js's exportResource() is not called from anywhere
in the UI. This is a missing feature (a button/menu item), not a test gap. Recommend
raising with Janaka/the team on whether export ships in the UI before this UAT case is
re-tested end to end."

| 2026-09-19 | UAT-17: model switch (ADJUSTED — only one model available) | Claude | 1 | 1 | 0 | 0 | 100% | `GET /api/models` right now returns exactly one `available: true` entry (`qwen25-3b`); the other (`legal-1.5b`) is `available: false` — its GGUF isn't built/on disk in this environment (matches the `.env.example` comment: it's a locally-built finetune that missed the ML track's acceptance gate, 0.557/0.621 vs. a 0.70 minimum). `ResourcesPanel.jsx` gates the "generator-model" `<select>` on `models.length > 1` (`models` already pre-filtered to `.available`), so with only one usable model **the selector does not render at all** — confirmed with a direct Cypress assertion (`cy.get("#generator-model").should("not.exist")`, passed) plus `UAT17-no-model-selector-only-one-available.png`. "Switch between the two configured models" as literally specified is not testable in this environment. |

**Scope note, UAT-17:** Not testable as specified — there is only one available model
in this environment, not two, so there is no selector to switch. Tested what does exist
instead: confirmed the one available model generates correctly (see UAT-18 below, same
model), and confirmed the gate-failed/unbuilt model is excluded from the UI entirely
(stronger than "never pre-selected as default" — it's not offered at all). Recommend
re-testing the actual two-model switch once `legal-1.5b`'s GGUF is built via
`scripts/build_finetuned_gguf.py` in this environment.

| 2026-09-19 | UAT-18: MCQ difficulty (easy/medium/hard) | Claude | 3 | 3 | 0 | 0 | 100% | Real generations, `evaluate: true`, full job JSON in `/tmp/uat18-results/mcq-{easy,medium,hard}.json`. **easy**: 2 attempts, judge scores 40 then 60 — never cleared the 70 threshold, `accepted: false` (would show the "flagged" badge in the UI). **medium**: 1 attempt, score 90, `accepted: true`. **hard**: attempt 1 rejected at the *validator* stage before the judge even ran ("correct_answer that is not one of its options" — a real structural catch); attempt 2 passed judge, score 90, `accepted: true`. Questions are visibly different in substance across levels (easy asks for a chapter number; hard asks for a "must vs. may" legal distinction) — not just a stored label. No "all of the above"/degenerate options anywhere. |
| 2026-09-19 | UAT-18: summary style (auto/narrative/structured) | Claude | 3 | 3 | 0 | 0 | 100% | `/tmp/uat18-results/summary-{auto,narrative,structured}.json`. **auto** and **narrative** are both flowing prose with genuinely different wording, both accepted at score 90. **structured** renders as a bulleted, bold-emphasized list (visibly different formatting, not just a label) but **did not clear the evaluator gate** (score 60, `accepted: false`) — a real, visible content-quality difference across styles, not a cosmetic one. |
| 2026-09-19 | Part 3: real chat turn with page-grounded citation | Claude | 1 | 1 | 0 | 0 | 100% | Fresh session, asked "According to section 40, how is every action ordinarily instituted?" — reply grounded in the source (`mode: "pdf"`, not general knowledge), judge `accepted: true, score: 100`, citation `{page: 1, paragraph: 1}` — matches the actual source location for section 40. `/tmp/uat18-results/part3-chat.json`. |
| 2026-09-19 | Part 3: real MCQ generation, quality check | Claude | 1 | 1 | 0 | 0 | 100% | 4 questions, `evaluate: true`, passed judge on the *first* attempt, score 90, `accepted: true`. All 4 questions have genuinely distinct, content-grounded distractors — no degenerate "all/none of the above" pattern in any option set, consistent with the U-06 gate rules already unit-tested. `/tmp/uat18-results/part3-mcq.json`. |

## 2026-09-19 — R-14 remaining accessibility scope (Part 2)

Two real defects were found during this pass (details below the table). Evidence:
`test-reports/axe-summary.json` (10 entries), `/tmp/lh-results/*.json`/`*.html` (Lighthouse),
Cypress screenshots `cypress/screenshots/pipeline.cy.js/R14-keyboard-*.png` (gitignored, not
committed — local paths only).

**Discrepancies from the request, flagged as asked:**
- The 4 screens "already done" (dashboard/upload/chat/quiz) were **never actually tested in
  dark theme** — the existing `tests/accessibility.test.jsx` had no theme handling at all
  before this pass. Added it (a `.dark` class toggle on `<html>`, matching `useTheme.js`)
  for the 3 new screens as asked; the original 4 remain light-only unless the team wants
  them backfilled too.
- "Same bar as before: includedImpacts serious/critical" doesn't match what the existing
  4-screen pattern actually asserts: it fails on **any** violation under the given WCAG
  tags, at any impact level (no impact filtering at all — `jest-axe` returns whatever
  `axe-core` finds for those tags; `includedImpacts` isn't a filter it exposes). Kept the
  same (stricter) actual mechanism for consistency rather than introducing a filter that
  wasn't really there before.

| Date | Item/suite | Run by | Executed | Passed | Failed | Skipped | Pass % | Comments/defects |
|------|-----------|--------|----------|--------|--------|---------|--------|-------------------|
| 2026-09-19 | axe: login, reader, resource-view/flashcards (light+dark) | Claude | 6 | 6 | 0 | 0 | 100% | Extended `tests/accessibility.test.jsx` in place, matching its exact existing jest-axe/jsdom pattern (not cypress-axe — "however you ran it for the 4 screens already done"). Zero violations at any impact, any of the 6 new checks (login × 2 themes, reader × 2, flashcards × 2). One real environment issue hit and fixed along the way: `DocumentReader` rendered with `sourceKind="pdf"` produces a raw `<iframe>`, and axe-core cannot cross into a fake jsdom iframe at all ("Respondable target must be a frame in the current window" — an axe/jsdom error, not a violation) — switched the reader audit to `sourceKind="tex"` so it exercises the "Text" mode DocumentReader actually renders and controls, which is the real accessibility surface (the PDF tab is opaque browser-native rendering either way). Full Vitest suite: 54/54 passing afterward. |
| 2026-09-19 | Contrast check: body text, citation chips, buttons (light+dark) | Claude | 10 pairs | 9 | 1 | 0 | 90% | Computed directly from the actual CSS custom-property values in `src/index.css` using the exact WCAG relative-luminance formula (same math WebAIM's checker uses) rather than relying on jsdom's limited paint engine. 9/10 pairs pass ≥4.5:1 (light body 8.09:1, light citation chip 13.54:1, light button 7.29:1, dark body 8.41:1, dark citation chip 10.81:1, dark citation page-number 5.51:1, etc.). **1 real failure — see DEFECT 1 below.** |
| 2026-09-19 | Lighthouse accessibility: homepage, login, dashboard, upload | Claude | 4 | 4 | 0 | 0 | 100%* | Real scores via Puppeteer + Lighthouse's programmatic API: homepage 85, login 90, dashboard 95, documents/upload 95. \*"Passed" here means the audit ran successfully and produced a report, not a perfect score — see findings below the table; every one of these 4 has at least one real Lighthouse-flagged issue. |
| 2026-09-19 | Lighthouse accessibility: reader, chat, resources×2 (BLOCKED) | Claude | 0 | 0 | 0 | 4 | N/A | **Not completed — a diagnosed, genuine tooling limitation, not a product issue.** Every attempt to audit these 4 authenticated screens (Puppeteer-driven real Keycloak login, a persistent Chrome-for-Testing profile via `--user-data-dir`, `--disable-storage-reset`) resulted in Lighthouse instead auditing **Keycloak's own hosted login page** — confirmed by inspecting each report's `finalDisplayedUrl` (all four pointed at `localhost:8081/realms/.../auth`, not the app) and, decisively, by directly checking the profile's cookie jar after a completed login: **zero cookies persisted for either `localhost:5173` or `localhost:8081`**, even immediately after a confirmed-successful login. Chrome-for-Testing's headless/`--no-sandbox` profile does not appear to persist cookies to disk reliably in this sandbox across separate process launches, which is what this technique depends on. This is a tooling/environment limitation specific to combining Lighthouse with this app's real-SSO-cookie-dependent auth — not evidence these screens are broken (they render and pass axe/Cypress correctly elsewhere in this same pass). Needs a non-sandboxed machine or CI runner with working cookie persistence, or a Lighthouse "user flow" approach using a single continuously-open authenticated tab rather than separate process launches. |
| 2026-09-19 | Keyboard-only walk: login → dashboard → upload → chat → generate | Claude | 5 | 4 | 1 | 0 | 80% | No `cypress-real-events`/`cypress-plugin-tab` in this project, so a literal physical Tab keypress could not be simulated; each stop calls `.focus()` on the element a Tab press would reach next, screenshots the result, and the screenshot is inspected directly (an initial computed-style heuristic gave a false failure on the very first element despite a plainly visible ring in its own screenshot — dropped in favor of direct visual inspection, which the instructions' "written walkthrough" alternative allows). **4/5 show a clear, visible focus ring** (dashboard nav logo link, chat message composer, resource-type select — screenshots named `R14-keyboard-{dashboard-nav-link,chat-input,generate-resource-type-select}.png`). **1/5 — the upload file input — shows no visible focus indicator at all: see DEFECT 2 below.** Login itself (the real Keycloak hosted form) uses native browser inputs with the browser's own default focus ring — that's Keycloak's theme, not this app's CSS, so it's out of this app's scope and not counted above. |
| 2026-09-19 | Screen reader: streamed chat answer via ARIA live region | Claude | 0 | — | — | 1 | N/A | **Structural check done; full pass not possible in this environment.** `grep -rn "aria-live\|role=\"status\"\|role=\"alert\"" src/` across the entire frontend returns **zero matches** — there is no ARIA live region anywhere in the codebase. Read `StreamingMessage.jsx` in full to confirm directly: the streaming text, cursor, and stage messages ("Retrieving...", "Generating...") are plain `<div>`/`<p>` elements with no `aria-live`, `role`, or equivalent. This means a screen reader user gets **no announcement at all** as an answer streams in — confirmed structurally, not run against a real screen reader. **Could not run an actual NVDA/JAWS pass** — neither exists on macOS, and there was no way to drive/record a VoiceOver session through the tools available here. Filed as a scope gap, not faked. |

**Lighthouse per-screen findings (the 4 completed screens):**

| Screen | Score | Failing audits |
|---|---:|---|
| Homepage | 85 | `color-contrast`, `heading-order` (headings skip a level), `target-size` (a touch target is too small/too close to others) |
| Login | 90 | `color-contrast`, `html-has-lang` (see note) |
| Dashboard | 95 | `color-contrast` |
| Documents (upload) | 95 | `color-contrast` |

`color-contrast` failing on **every** screen corroborates DEFECT 1 below independently —
Lighthouse found it live in the browser, the manual WCAG computation found the same thing
from the CSS source. The `html-has-lang` flag on login specifically is very likely a
timing artifact rather than a real gap: `index.html` does have `<html lang="en">`
(confirmed via `curl` and live DOM inspection on other routes), but `login.jsx`'s whole
job is to redirect to Keycloak immediately, and Lighthouse may have captured the audit
mid-navigation, after the browser had already moved toward Keycloak's own page. Not
re-verified further given the tooling limitations already hit elsewhere in this pass;
worth a quick manual recheck rather than treating as confirmed.

### DEFECT 1 — dark-theme primary button text fails WCAG AA contrast

**Severity:** Medium (a real, measurable WCAG 2.1 AA 1.4.3 failure — not a security issue)
**Component:** `integrated-frontend/src/index.css`, `.btn-primary` (dark theme)
**Found during:** R-14 contrast check, 19 Sep 2026

White button text (`#fff`) on dark theme's `--color-primary` (`#7B93F0`) computes to
**2.89:1** — well under the 4.5:1 requirement for normal text, and still under even the
more lenient 3:1 "large text" allowance (the button's `font-size: var(--font-size-sm)` at
`font-weight: 600` does not qualify as large text regardless). Computed via the exact WCAG
relative-luminance formula from the actual CSS custom-property values, not a tool estimate.
Every other checked pair (body text, citation chips, citation page-numbers, light-theme
buttons) passes comfortably — this is specifically the dark-theme filled-button case.
**Not fixed in this pass** — a color change is a design decision; flagging with the exact
number for the team to pick a fix (e.g. a darker dark-mode button background, or dark
button text instead of white) rather than changing the palette unilaterally.

### DEFECT 2 — upload control has no visible keyboard focus indicator

**Severity:** Medium (WCAG 2.1 AA 2.4.7 Focus Visible)
**Component:** `integrated-frontend/src/components/DocumentsCard.jsx`
**Found during:** R-14 keyboard-only walk, 19 Sep 2026

The upload dropzone's real `<input type="file">` is styled `className="sr-only"` (visually
hidden, standard practice so the custom dropzone graphic is what's seen) — but nothing else
picks up its focus state. `grep -n "focus-within" src/index.css` and the component itself:
no matches. Confirmed by screenshot (`R14-keyboard-upload-file-input.png`): after
`.focus()` on the input, the dropzone looks completely unchanged from its resting state —
compare against the other 3 keyboard-walk screenshots, which all show a clear ring. A
keyboard-only user tabbing to the upload control has no way to see that it is focused.
**Not fixed in this pass** — recommended fix: a `:focus-within` (or `:has(:focus-visible)`)
rule on the dropzone's wrapping element mirroring the existing drag-active style
(`border-primary bg-primary-soft`), so keyboard focus gets the same visible treatment drag
hover already gets.

## 2026-09-19 — Journey B (R-13) de-flaked: message seeded via API instead of typed in the UI

**Affects:** `integrated-frontend/cypress/e2e/pipeline.cy.js`, Journey B ("resume an older
conversation, continue it, then delete it")

Journey B's follow-up message was previously typed into the composer and sent through the
UI, which calls `sendMessage()` with its default `evaluate: true` — the judged path.
`app/routers/chat.py`'s own docstring states this plainly: "rewrite the question against
the history, retrieve, generate, judge, retry once if the judge rejected it. That is
30-60 seconds on the local backend." `src/api/jobs.js`'s `waitForJob` comment says the same
thing from the frontend side: once the reply text is settled (`reply_ready`), "the judge
holds the turn for another 25-50s" before the job — and the persisted message row — is
actually done. Journey B's reload happens well inside that window, past the suite's 15s
default command timeout, which is what was actually being hit.

This refines, rather than replaces, the write-after-read-lag defect logged above (19 Sep,
R-13 first live run / R-08 diagnostic): that instrumentation was real and reproducible
(658ms-1449ms measured), but was already flagged there as "notably shorter than what alone
would explain Journey B's Cypress failures." The judge's 25-50s hold before persist is the
dominant cause the earlier note was missing; the small measured read lag is a real, separate,
minor effect on top of it, not something that needs its own further backend investigation.

**Confirming Step 1 of today's task:** Journey B asserted nothing judge-related before this
change — no score, no `accepted` flag, no quality badge, only the reply's text content and
a citation chip. So there is no judge coverage to relocate out of this journey; that coverage
already exists separately (see "Part 3: real chat turn with page-grounded citation" above,
which asserts `judge accepted: true, score: 100` on a real `evaluate: true` turn).

**The fix does not touch the judge's actual latency** — it works around it for this journey,
which is about resume/reload/delete, not about the judge. The follow-up message is now
seeded with a direct `cy.request()` POST to `/api/chat/sessions/{id}/messages` with
`evaluate: false` (the backend's real, intentional escape hatch — see
`learnmate/chat_agent/evaluate.py`: `evaluate=False` auto-passes with no judge call at all),
then polled via a new `waitForJobDone()` helper (mirroring `src/api/jobs.js`'s own
`waitForJob`, since no job-polling helper already existed in this Cypress spec to reuse)
until the job is `done`. Only then does the UI-driven part of the journey run: reload,
assert both messages survived, delete the conversation, confirm it's gone. That UI-driven
part — the actual subject of this journey — is unchanged.

**Verification:** Journey B run in isolation 3 times in a row (reseeding a fresh
conversation via direct API calls before each run, since the journey deletes its own
conversation at the end and isn't otherwise repeatable from a cold state) — all 3 passed,
~8s Cypress-reported duration each time. Full `pipeline.cy.js` suite run once afterward:
**9/9 passing** — the first time this session Journey B has passed as part of a full-suite
run rather than being the suite's one known failure.

One process note: `docs/feature-adders/LATENCY_QUALITY_FAILURES.md` and a "Master Test
Plan" performance section, both referenced when this task was assigned, do not exist
anywhere in this repository (checked by filename and by content search). The 30-60s judge
latency claim itself checks out independently, straight from `app/routers/chat.py`'s and
`src/api/jobs.js`'s own comments quoted above, so this did not block the fix — but the
specific documents named are not where that finding actually lives, and it's worth knowing
that plan doesn't exist under that name here.

### Addendum, same day — original failure text recovered, and confirmed against Step 1

The paragraph above described the failure narratively ("Journey B's reload happens well
inside that window, past the suite's 15s default command timeout") without quoting the
actual Cypress error. Three saved terminal logs from tonight's earlier debugging survived
in `/private/tmp` (`cypress-journeyB-final.log`, `cypress-journeyB-fixed2.log`,
`cypress-journeyB-instrumented.log` — all clean, isolated runs with a valid prior Journey A
state), and all three reproduce the identical error, verbatim:

```
AssertionError: Timed out retrying after 15000ms: Expected to find content: 'What must the plaint contain' but never did.
    at Context.eval (webpack://learnmate-frontend/./cypress/e2e/pipeline.cy.js:129:50)
```

Total run duration in all three: 37-39 seconds. This confirms the diagnosis precisely, and
sharpens it: the two assertions that actually had generous `{ timeout: 600_000 }` overrides
(the reply text and the `.cite` chip) were *not* what failed — they passed, because the real
generation+judge time is well under 10 minutes. What failed is the very next line, checking
the *user's own question text* survived reload, which — being unremarkable, ordinary
content — had no timeout override and used Cypress's 15000ms default. That default is far
shorter than the judge's 25-50s hold before persist, so it fails reliably. This is a clean,
bounded, fully-explained 15-second timeout, not a hang, not a job failure, and not a
different, unrelated assertion in any sense that undermines the judge-latency explanation —
it's a second, previously-unquoted piece of evidence for the exact same root cause. No
correction to the framing is needed; the explanation stands, now with the real error text
behind it instead of just prose.

One more log surfaced in the same search and is worth recording even though it doesn't
change the above: `cypress-journeyAB-debug4.log`, timestamped 18:04, shows Journey A passing
normally and then the run's own final summary reporting **`Duration: 315 minutes, 30
seconds`**, ending in `SIGTERM received` and an Electron renderer crash rather than a normal
Cypress assertion failure. This is real, recovered evidence, not fabricated — but nothing
in the log shows what (if anything) Journey B was doing during those ~5 hours; there is no
intermediate output at all between Journey A finishing and the SIGTERM. Its own timestamp
lines up almost exactly with the tail end of an earlier debugging cluster from 12:38-12:47
that same day, which strongly suggests this was a background `cypress run` left unattended
across other work in this session rather than a reproducible hang in the app or the test
itself — three separate later runs against the same code all completed cleanly in under 40
seconds. Recorded here for completeness rather than treated as a second defect: if it
recurs on a run nobody walks away from, it deserves its own investigation, but one
unexplained 5-hour outlier against three consistent 38-second reproductions isn't enough to
file as a finding on its own.
