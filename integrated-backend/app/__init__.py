"""
The web layer: a multi-user HTTP API over the LearnMate engine.

`learnmate/` is a single-user library -- ingest a PDF, ask it questions, generate study
material from it. This package is what turns that into a service several students can use
at once:

    config.py    the web half of the settings; the engine half is learnmate/config.py
    errors.py    engine exceptions -> HTTP status codes, in one place
    deps.py      the get_current_user dependency every protected route depends on
    schemas.py   request and response models

    auth/        accounts: hashing, tokens, registration and login rules
    jobs/        the background worker, because local inference is far slower than a
                 request can wait for
    services/    the work itself, called by routers and by the job worker alike
    routers/     the endpoints, which validate input and delegate

The rule the layering exists to enforce: a router never touches the engine or the database
directly, and a service never raises an HTTPException. Access control lives in
services/ownership.py and is checked on every path that names a document, session or
resource.
"""
