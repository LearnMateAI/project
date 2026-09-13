# Integration suites

Slim FastAPI app (same routers, **no** lifespan / GGUF). Mongo is mocked.

| File | Plan ID | What it tests |
|------|---------|---------------|
| `test_auth_api.py` | I-01 | register / login / me |
| `test_documents_api.py` | I-02 | 401, 400, 202 upload shape |
| `test_jobs_api.py` | I-03 | job 401 / 404 / 403 / 200 |
| `test_chat_resources_auth.py` | I-04 | chat/resources auth + 202 message |
| `test_cors_and_root.py` | I-05 | CORS + `GET /` |
