"""
End-to-end check against a running server.

    python scripts/smoke_test.py path/to/some.pdf

Registers a throwaway account, uploads a PDF, waits for it to be ingested, generates key
points and a set of MCQs, opens a chat session and asks two questions -- the second a
follow-up, to check that pronoun rewriting works -- then reads the analytics back.

A plain `requests` script rather than a test framework, because what it verifies is that
the whole system is wired together and reachable: a real server, a real MongoDB, a real
Qdrant and a real 3B model. That is not a unit test, and pretending it is by putting it
under pytest would invite someone to run it in CI where none of those exist.

It is slow on the local backend. Expect several minutes, most of it the first model load.
Pass --fast to skip evaluation (the judge is roughly half the wall clock).
"""

import argparse
import functools
import json
import sys
import time
import uuid
from pathlib import Path

import requests

# Unbuffered, so a run piped to a file or a CI log shows each step as it happens rather
# than dumping everything at the end. This script's whole value is the running commentary
# during the minutes a local generation takes.
print = functools.partial(print, flush=True)  # noqa: A001

BASE_URL = "http://localhost:8000"

# Generous, because "slow" and "hung" look identical from here and the local backend is
# genuinely slow: a first-ever run also downloads ~4 GB of model weights.
JOB_TIMEOUT = 1800
POLL_SECONDS = 2

_passed = 0
_failed = 0


def step(name: str, ok: bool, detail: str = "") -> bool:
    """Print one result line and keep score."""
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        _failed += 1
        print(f"  FAIL  {name}" + (f"  ({detail})" if detail else ""))
    return ok


class Client:
    """The API, with the token attached once instead of on every call."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def set_token(self, token: str) -> None:
        self.session.headers["Authorization"] = f"Bearer {token}"

    def request(self, method: str, path: str, **kwargs):
        return self.session.request(method, f"{self.base_url}{path}", timeout=120,
                                    **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def wait_for_job(self, job_id: str, label: str):
        """
        Poll one job to completion, printing progress as it changes.

        Returns the finished job record. Raises on failure or timeout, because every
        later step depends on this one having worked.
        """
        deadline = time.time() + JOB_TIMEOUT
        last_message = None

        while time.time() < deadline:
            response = self.get(f"/api/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()

            message = (job.get("progress") or {}).get("message")
            if message and message != last_message:
                print(f"        ... {message}")
                last_message = message

            if job["status"] == "done":
                return job
            if job["status"] == "failed":
                raise RuntimeError(f"{label} failed: {job.get('error')}")

            time.sleep(POLL_SECONDS)

        raise TimeoutError(f"{label} did not finish within {JOB_TIMEOUT}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="a PDF to ingest")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--fast", action="store_true",
                        help="skip the judge -- roughly halves the wall clock")
    parser.add_argument("--topic", default=None,
                        help="topic for the passage-scope generation")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"No such file: {args.pdf}")
        return 2

    evaluate = not args.fast
    client = Client(args.base_url)

    # --- 1. health ---------------------------------------------------------------------
    print("\n[1] Health")
    try:
        health = client.get("/api/health").json()
    except requests.RequestException as exc:
        print(f"  FAIL  cannot reach {args.base_url} ({exc})")
        print("        Start it with: uvicorn server:app --port 8000")
        return 1

    step("server reachable", True, health["status"])
    step("mongodb", health["checks"]["mongodb"]["ok"],
         health["checks"]["mongodb"].get("error", ""))
    step("vector store", health["checks"]["vectors"]["ok"],
         health["checks"]["vectors"].get("error")
         or health["checks"]["vectors"].get("detail", ""))
    if not health["checks"]["mongodb"]["ok"] or not health["checks"]["vectors"]["ok"]:
        print("\n  Databases are not up. Try: docker compose up -d")
        return 1

    # --- 2. accounts -------------------------------------------------------------------
    print("\n[2] Accounts")
    email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
    password = "smoketest123"

    response = client.post("/api/auth/register",
                           json={"name": "Smoke Test", "email": email,
                                 "password": password})
    step("register", response.status_code == 201, str(response.status_code))
    if response.status_code != 201:
        print(f"        {response.text[:300]}")
        return 1
    client.set_token(response.json()["token"])

    duplicate = client.post("/api/auth/register",
                            json={"name": "Smoke Test", "email": email,
                                  "password": password})
    step("duplicate email rejected", duplicate.status_code == 409,
         str(duplicate.status_code))

    weak = client.post("/api/auth/register",
                       json={"name": "x", "email": f"weak-{uuid.uuid4().hex[:6]}@e.com",
                             "password": "short"})
    step("weak password rejected", weak.status_code == 400, str(weak.status_code))

    bad_login = client.post("/api/auth/login",
                            json={"email": email, "password": "wrongpassword1"})
    step("wrong password rejected", bad_login.status_code == 401,
         str(bad_login.status_code))

    step("token works", client.get("/api/auth/me").status_code == 200)

    # --- 3. upload and ingest ----------------------------------------------------------
    print("\n[3] Upload and ingest")
    with args.pdf.open("rb") as handle:
        response = client.post(
            "/api/documents/upload",
            files={"file": (args.pdf.name, handle, "application/pdf")},
            data={"subject": "Smoke Test"},
        )
    if not step("upload accepted", response.status_code == 202,
                str(response.status_code)):
        print(f"        {response.text[:300]}")
        return 1

    accepted = response.json()
    document_id = accepted["document"]["id"]
    print(f"        document {document_id}")

    try:
        job = client.wait_for_job(accepted["job_id"], "Ingestion")
    except (RuntimeError, TimeoutError) as exc:
        step("ingestion", False, str(exc))
        return 1

    result = job["result"]
    step("ingestion", True,
         f"{result.get('pages')} pages, {result.get('chunks')} chunks, "
         f"{result.get('elapsed_s')}s"
         + (" (already indexed)" if result.get("skipped") else ""))

    documents = client.get("/api/documents").json()
    document = next((d for d in documents if d["id"] == document_id), None)
    step("document listed", document is not None)
    step("status Ready", bool(document) and document["processing_status"] == "Ready",
         document["processing_status"] if document else "")

    step("PDF downloadable",
         client.get(f"/api/documents/{document_id}/file").status_code == 200)
    pages = client.get(f"/api/documents/{document_id}/pages",
                       params={"first": 1, "last": 2}).json()
    step("cleaned page text", len(pages) > 0, f"{len(pages)} page(s)")

    # --- 4. passage-scope generation ---------------------------------------------------
    print("\n[4] Generate key points (passage scope)")
    response = client.post("/api/resources/generate", json={
        "document_id": document_id,
        "resource_type": "keypoints",
        "scope": "passage",
        "topic": args.topic,
        "count": 6,
        "evaluate": evaluate,
    })
    if not step("accepted", response.status_code == 202, str(response.status_code)):
        print(f"        {response.text[:300]}")
    else:
        try:
            job = client.wait_for_job(response.json()["job_id"], "Key points")
            resource = job["result"]
            points = resource.get("content") or []
            step("key points generated", len(points) > 0,
                 f"{len(points)} points, score {resource.get('score')}, "
                 f"accepted={resource.get('accepted')}")
            if points:
                print(f"        e.g. {str(points[0])[:110]}")
        except (RuntimeError, TimeoutError) as exc:
            step("key points generated", False, str(exc))

    # --- 5. document-scope generation --------------------------------------------------
    print("\n[5] Generate MCQs (document scope)")
    response = client.post("/api/resources/generate", json={
        "document_id": document_id,
        "resource_type": "mcq",
        "scope": "document",
        "count": 5,
        "evaluate": evaluate,
    })
    if not step("accepted", response.status_code == 202, str(response.status_code)):
        print(f"        {response.text[:300]}")
    else:
        try:
            job = client.wait_for_job(response.json()["job_id"], "MCQs")
            resource = job["result"]
            questions = resource.get("content") or []
            step("MCQs generated", len(questions) > 0,
                 f"{resource.get('generated')} of {resource.get('requested')} asked for, "
                 f"across {resource.get('groups')} group(s)")
            if questions:
                first = questions[0]
                step("MCQ well-formed",
                     isinstance(first, dict) and len(first.get("options", [])) == 4
                     and first.get("correct_answer") in first.get("options", []),
                     str(first.get("question", ""))[:80])
        except (RuntimeError, TimeoutError) as exc:
            step("MCQs generated", False, str(exc))

    listed = client.get("/api/resources", params={"document_id": document_id}).json()
    step("resources listed", len(listed) >= 1, f"{len(listed)} resource(s)")

    # --- 6. chat -----------------------------------------------------------------------
    print("\n[6] Chat")
    response = client.post("/api/chat/sessions",
                           json={"document_id": document_id, "title": "Smoke test"})
    if not step("session created", response.status_code == 201,
                str(response.status_code)):
        print(f"        {response.text[:300]}")
    else:
        session_id = response.json()["session_id"]

        for label, question in (
            ("first question", "What is this document about?"),
            # A pronoun with no antecedent in the question itself: only resolvable
            # against the history, which is what the rewrite node is for.
            ("follow-up rewritten", "What else does it say about that?"),
        ):
            response = client.post(f"/api/chat/sessions/{session_id}/messages",
                                   json={"message": question, "evaluate": evaluate})
            if response.status_code != 202:
                step(label, False, response.text[:200])
                continue
            try:
                job = client.wait_for_job(response.json()["job_id"], label)
                answer = job["result"]
                step(label, bool(answer.get("reply")),
                     f"mode={answer.get('mode')}, top_score="
                     f"{round(answer.get('top_score') or 0, 3)}, "
                     f"score={answer.get('score')}")
                print(f"        Q: {question}")
                if answer.get("standalone_query") != question:
                    print(f"        rewritten: {answer.get('standalone_query')}")
                print(f"        A: {str(answer.get('reply'))[:160]}")
            except (RuntimeError, TimeoutError) as exc:
                step(label, False, str(exc))

        messages = client.get(f"/api/chat/sessions/{session_id}/messages").json()
        step("transcript stored", len(messages) >= 4, f"{len(messages)} turns")

    # --- 7. isolation ------------------------------------------------------------------
    print("\n[7] Isolation between users")
    other = Client(args.base_url)
    response = other.post("/api/auth/register", json={
        "name": "Other User",
        "email": f"smoke-other-{uuid.uuid4().hex[:8]}@example.com",
        "password": "smoketest123",
    })
    if response.status_code == 201:
        other.set_token(response.json()["token"])
        step("other user's library is empty",
             other.get("/api/documents").json() == [])
        step("cannot read the document",
             other.get(f"/api/documents/{document_id}").status_code == 404)
        step("cannot download the file",
             other.get(f"/api/documents/{document_id}/file").status_code == 404)
        step("cannot list its resources",
             other.get("/api/resources",
                       params={"document_id": document_id}).status_code == 404)
    else:
        step("second account", False, str(response.status_code))

    # --- 8. analytics ------------------------------------------------------------------
    print("\n[8] Analytics")
    analytics = client.get("/api/analytics").json()
    step("analytics", analytics.get("documents", 0) >= 1,
         json.dumps({"documents": analytics.get("documents"),
                     "resources": analytics.get("resources", {}).get("total"),
                     "messages": analytics.get("messages")}))

    print(f"\n{'=' * 60}\n  {_passed} passed, {_failed} failed\n{'=' * 60}")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
