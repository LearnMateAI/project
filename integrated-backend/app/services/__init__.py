"""
The work itself: everything the routers and the job worker both need.

Services sit between the two so that the same function serves an HTTP request and a
background job without either one knowing about the other. That is why nothing in here
imports FastAPI or raises an HTTPException -- it raises AccessDenied, NotFound or a plain
ValueError, and app/errors.py decides what those mean over HTTP.

    ownership.py  the access checks, in one place, used by all the others
    documents.py  upload, list, read and delete PDFs
    resources.py  generating study material, and reading it back
    chat.py       sessions and turns
    analytics.py  what one user has done, and how well it scored
"""
