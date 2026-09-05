"""
Request and response models.

Requests are modelled strictly, because that is where a typo becomes a 422 with a useful
message instead of a confusing failure three layers down. Responses are mostly left as
plain dicts built by the services: generated content is genuinely polymorphic -- a summary
is a string, key points are a list of strings, MCQs are a list of objects -- and a model
that says `Any` is documentation theatre.

The field names here are the ones the React frontend already sends and reads
(`document_id`, `resource_type`, `upload_date`, `page_count`), kept deliberately so the
migration is additive rather than a rewrite.
"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from learnmate.resource_agent import TASK_NAMES


# --- Auth ------------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    # Length is checked in app/auth/users.py so the rule and its message live together;
    # this bound only stops a megabyte of "password" reaching bcrypt.
    password: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserView(BaseModel):
    id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    token: str
    user: UserView


# --- Resources -------------------------------------------------------------------------

# What a client may ask for. The engine's four task names, plus the two the frontend
# already sends -- resolved in services/resources.py so an in-flight frontend keeps
# working while it is being updated.
RESOURCE_TYPES = tuple(TASK_NAMES) + ("key_points", "explanation_summary")


class GenerateRequest(BaseModel):
    """
    One generation request.

    `scope` is the choice that matters, and it is not a performance knob:

        passage   one continuous extract, optionally the pages most relevant to `topic`.
                  Seconds to a minute. This is "five questions about directors' duties".
        document  the whole PDF, read in groups and pooled (or, for a summary, summarised
                  per page and folded). Minutes. This is "forty questions about this book".
    """

    document_id: str
    resource_type: str = Field(description=f"one of {list(RESOURCE_TYPES)}")
    scope: str = Field(default="passage", pattern="^(passage|document)$")

    # --- passage scope ---
    topic: Optional[str] = Field(default=None, max_length=300)
    pages: Optional[List[int]] = None

    # --- how many ---
    # Meaning depends on the task: questions for mcq and practice_qsn, points for
    # keypoints, roughly sentences for summary. None lets the engine size it.
    count: Optional[int] = Field(default=None, ge=1, le=200)
    # Document scope only, and mutually exclusive with count: a rate reads every page,
    # a total samples across the document.
    per_page: Optional[int] = Field(default=None, ge=1, le=10)

    # --- evaluation ---
    # False skips both gates. Roughly halves the time, and the result is unreviewed.
    evaluate: bool = True
    threshold: Optional[int] = Field(default=None, ge=0, le=100)
    # Additive; omitted = current behaviour (narrative summary, medium MCQs, default model).
    summary_style: Optional[str] = Field(default=None, pattern="^(narrative|structured|auto)$")
    difficulty: Optional[str] = Field(default=None, pattern="^(easy|medium|hard)$")
    model_id: Optional[str] = Field(default=None, max_length=80)


# --- Chat ------------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    document_id: str
    title: Optional[str] = Field(default=None, max_length=200)


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    # False skips the judge: a faster reply, not reviewed for hallucination.
    evaluate: bool = True
    model_id: Optional[str] = Field(default=None, max_length=80)


# --- Jobs ------------------------------------------------------------------------------

class JobAccepted(BaseModel):
    """What every long-running endpoint returns instead of making the client wait."""

    job_id: str
    status: str
    kind: str
