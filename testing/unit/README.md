# Unit suites

Each file is one named suite from `PLAN.md`. Run one suite:

```bash
python -m pytest testing/unit/test_auth_security.py -q
```

| File | Plan ID | What it tests |
|------|---------|---------------|
| `test_auth_security.py` | U-01 | bcrypt + JWT |
| `test_password_rules.py` | U-02 | password policy |
| `test_schemas.py` | U-03 | request models |
| `test_object_ids.py` | U-04 | ObjectId coercion |
| `test_evaluator_normalise.py` | U-05 | `norm()` |
| `test_evaluator_mcq.py` | U-06 | MCQ gate 1 |
| `test_evaluator_text.py` | U-07 | summary / keypoints / practice |
| `test_chat_decide.py` | U-08 | chat retry vs persist |
| `test_resource_decide.py` | U-09 | resource retry vs persist |
| `test_pdf_validate.py` | U-10 | upload rejection |
| `test_chunking.py` | U-11 | clean + TOC skip + chunks |
| `test_email_and_tasks.py` | U-12 | email + task registry |
| `test_safe_filename.py` | U-13 | header-safe filenames |
| `test_frontend_contracts.py` | U-14 | React API paths / routes |
| `test_error_handlers.py` | U-15 | HTTP status mapping |
