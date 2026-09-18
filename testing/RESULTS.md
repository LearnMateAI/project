# Last recorded pytest results

Branch: `testing`, merged forward to `origin/main` + `thevindu-feature` (see PROCESS.md
§6). Command run from the repository root.

| Date | Command | Passed | Failed | Skipped | Notes |
|------|---------|--------|--------|---------|-------|
| 2026-08-19 | `python -m pytest testing/unit testing/integration testing/uat --tb=line` | 97 | 0 | 4 | Original suite, predates the feature-adders work below. |
| 2026-09-18 | `python -m pytest testing/unit testing/integration testing/uat --tb=line` | **148** | 0 | **4** | After merging `origin/main` (BM25 hybrid, multi-model, office ingestion, export) and `thevindu-feature` (chat rename/resume, document reader, past-uploads reopen). 3 pre-existing assertions updated to match intentional message changes; 51 new tests added — see "New this run" below. |
| 2026-09-18 | `python -m pytest integrated-backend/tests -q` (separate suite; run from `integrated-backend/`) | **29** | 0 | 0 | Not under `testing/pytest.ini`; written directly against real imports (still no Mongo/Qdrant/GGUF). See PLAN.md §9. |

**Combined: 177 passed, 0 failed, 4 skipped (live UAT only).**

## Layer breakdown

| Layer | Result |
|-------|--------|
| Unit (`testing/unit`) | all passed |
| Integration (`testing/integration`) | all passed |
| UAT (`testing/uat`) | 4 skipped until `LEARNMATE_UAT=1` and API `:8010` (not attempted this run — no live Docker/Mongo/Qdrant/GGUF stack in this environment) |
| `integrated-backend/tests` (office extract, chat sessions, latency/quality) | all passed |

## Three assertions fixed (stale, not regressions)

Merging forward exposed three `testing/unit` assertions written against the old
PDF-only upload path. In each case the product behaviour is the intended new behaviour
(multi-format ingestion), and the test was updated to match it — not a defect:

| Test | Old expectation | New (correct) behaviour |
|------|------------------|--------------------------|
| `test_pdf_validate.py::test_non_pdf_extension_rejected` | message matched `"Only PDF"` | `.txt` now gets the multi-format guidance: "Upload a PDF, Word (.docx), PowerPoint (.pptx), or LaTeX (.tex) file." |
| `test_pdf_validate.py::test_garbage_bytes_are_corrupt` | message matched `"could not be read"` | A cheap magic-byte check now rejects non-`%PDF` bytes *before* PyMuPDF ever opens them: "This file is not a readable PDF." A new test (`test_pdf_header_with_corrupt_body_is_rejected`) restores coverage of the original "could not be read" branch using bytes that pass the magic-byte check but still fail to parse. |
| `test_frontend_contracts.py::test_upload_client_enforces_ten_megabytes` | source matched `"Only PDF files are accepted"` | `DocumentsCard.jsx` now shows the same multi-format message as the backend. |

## New this run (51 tests, 9 new files)

| File | Covers |
|------|--------|
| `unit/test_models_registry.py` | Registry parsing, real-file load, **the "no failed-gate default" safety rule** (`selectable_default` forced `false` when `experimental: true`, even if the YAML says otherwise), `get_entry`, `public_models` never leaking `gguf_path`/`resolved_path` |
| `unit/test_export_resource.py` | docx/pptx generation for summary (narrative + structured), MCQ, keypoints; format validation; default format |
| `unit/test_hybrid_retrieve.py` | BM25/ANN merge dedup-by-chunk-key, `"both"` tagging, `BM25_ANN_KEEP` cap, empty-merge case |
| `unit/test_chat_service.py` | `rename_session` rejects a whitespace-only title (schema alone does not — see below), strips/truncates, propagates a storage miss |
| `unit/test_mcq_difficulty.py` | `resolve_difficulty` tier resolution and its default-to-medium fallback |
| `unit/test_schemas.py` (extended) | `summary_style` / `difficulty` pattern validation; documents that `RenameSessionRequest` accepts a whitespace-only title (min_length=1 only) |
| `unit/test_frontend_contracts.py` (extended) | `DocumentsCard.jsx` accepts docx/pptx/tex extensions and MIME types |
| `integration/test_models_api.py` | `GET /api/models` 401 / 200, no filesystem paths leaked over HTTP |
| `integration/test_chat_sessions_api.py` | `PATCH /api/chat/sessions/{id}` 401 / 422 / 200 / 400, `GET /api/chat/sessions` 401 / 200 |
| `integration/test_resources_export_api.py` | `GET /api/resources/{id}/export` 401 / 422 (bad format) / 200 (Content-Disposition) / 404 (not owned) / 400 |
| `integration/test_document_reopen_api.py` | `GET /api/documents/{id}`, `/file`, `/pages` — 401 / 404 / 200, and that a filename with quotes/CR/LF cannot inject extra HTTP headers |

## Known gaps (not attempted, see PLAN.md §9 and docs/TEST_REPORT.md)

- Gate 2 judge behaviour for MCQ difficulty/distractor-checker and summary-style rubric
  lines — needs a live judge GGUF, out of scope for this pytest gate by design.
- No frontend component/unit test runner is configured (`integrated-frontend/package.json`
  has no `test` script, no Vitest/Jest, no Testing Library) — `test_frontend_contracts.py`
  only greps compiled source text, it does not render components.
- Live UAT (A-01…A-10 and the new document-reader / rename / reopen journeys) not run —
  no Docker/Mongo/Qdrant/GGUF stack available in this environment.
- Deployment/CI configuration on `origin/deployment`, `origin/dinura-deployment`,
  `origin/dinura-feedback-deploy` (Docker, Nginx, AWS SSM `deploy.yml`) has no automated
  tests anywhere in the repo.

## How to re-run

```bash
pip install -r testing/requirements.txt
python -m pytest testing/unit testing/integration testing/uat -q

# separate suite, real imports, run from integrated-backend/
cd integrated-backend && python -m pytest tests -q
```
