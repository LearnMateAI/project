"""
The endpoints.

    auth.py       /api/auth        register, log in, who am I
    documents.py  /api/documents   upload, list, read, delete
    resources.py  /api/resources   generate study material, read it back
    chat.py       /api/chat        sessions and turns
    jobs.py       /api/jobs        how is that long-running thing going
    analytics.py  /api/analytics   what this user has done, and how it scored

Routers validate input, check nothing themselves, and delegate to app/services. Access
control lives in services/ownership.py; error mapping lives in app/errors.py. A handler
that grew an `if` about who owns what would be the sign that a rule had escaped the one
place it is supposed to live.

Every endpoint except register and login depends on `get_current_user`.
"""

from . import analytics, auth, chat, documents, jobs, models, resources

__all__ = ["analytics", "auth", "chat", "documents", "jobs", "models", "resources"]
