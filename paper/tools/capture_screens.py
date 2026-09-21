"""
Capture the paper's screenshots from the running app.

    python paper/tools/capture_screens.py --api http://127.0.0.1:8010 --ui http://localhost:5173

Needs: the API running against the evaluation stores with the answer cache on, the Vite dev
server pointed at it, the simulated class already written (python -m eval.heatmap_bench), and
Playwright (`pip install playwright`; it drives the installed Microsoft Edge, so no browser
download is needed).

What it does, as a real user would:
  1. registers a demo student and uploads the Contract Law chapter (recognised by hash --
     no re-processing), opens a chat session;
  2. asks a question (full pipeline: seconds to a minute or two on CPU), then a paraphrase
     of it (served from the verified cache);
  3. opens the chat and the workspace's Class insights tab in Edge, clicks the hottest
     page, and saves figures/screens/chat.png and figures/screens/workspace.png.
"""

import argparse
import json
import time
import uuid
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SCREENS = HERE.parent / "figures" / "screens"
CORPUS = HERE.parents[1] / "integrated-backend" / "data" / "eval_corpus"


def api_session(api: str):
    http = requests.Session()
    name = f"Demo Student {uuid.uuid4().hex[:4]}"
    auth = http.post(f"{api}/api/auth/register", timeout=60,
                     json={"name": name, "email": f"demo-{uuid.uuid4().hex[:8]}@example.com",
                           "password": "Demo-password-123"}).json()
    http.headers["Authorization"] = f"Bearer {auth['token']}"
    return http, auth


def wait(http, api, job_id, timeout=1800):
    started = time.time()
    while time.time() - started < timeout:
        job = http.get(f"{api}/api/jobs/{job_id}", timeout=60).json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(1.0)
    raise TimeoutError(job_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8010")
    parser.add_argument("--ui", default="http://localhost:5173")
    parser.add_argument("--chapter", type=int, default=7)
    parser.add_argument("--question", default="What makes a contract legally enforceable?")
    parser.add_argument("--paraphrase",
                        default="What does a contract need in order to be enforceable?")
    args = parser.parse_args()

    manifest = json.loads((CORPUS / "corpus.json").read_text(encoding="utf-8"))
    entry = next(d for d in manifest["documents"] if d["chapter"] == args.chapter)
    pdf = CORPUS / "docs" / entry["filename"]

    http, auth = api_session(args.api)
    with pdf.open("rb") as handle:
        upload = http.post(f"{args.api}/api/documents", timeout=120,
                           files={"file": (pdf.name, handle, "application/pdf")}).json()
    wait(http, args.api, upload["job_id"])
    doc_id = upload["document"]["id"]
    session = http.post(f"{args.api}/api/chat/sessions", timeout=60,
                        json={"document_id": doc_id, "title": entry["title"]}).json()
    sid = session["session_id"]
    for text in (args.question, args.paraphrase):
        job = http.post(f"{args.api}/api/chat/sessions/{sid}/messages", timeout=60,
                        json={"message": text}).json()
        result = wait(http, args.api, job["job_id"]).get("result") or {}
        print(f"  {text!r}: mode={result.get('mode')} score={result.get('score')} "
              f"cache={result.get('cache')}")

    from playwright.sync_api import sync_playwright

    SCREENS.mkdir(parents=True, exist_ok=True)
    init = ("localStorage.setItem('token', %s);"
            "localStorage.setItem('user', %s);"
            "localStorage.setItem('authProvider', 'local');"
            % (json.dumps(auth["token"]), json.dumps(json.dumps(auth["user"]))))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1440, "height": 900},
                                device_scale_factor=2)
        page.add_init_script(init)

        page.goto(f"{args.ui}/chat/{sid}")
        page.wait_for_selector("text=Verified answer reused", timeout=60000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENS / "chat.png"))

        page.goto(f"{args.ui}/documents?open={doc_id}")
        page.get_by_role("button", name="Class insights").click()
        page.wait_for_selector(".heat-cell", timeout=120000)
        cells = page.locator(".heat-cell:not(.is-suppressed)")
        hottest, best = None, -1.0
        for i in range(cells.count()):
            heat = float(cells.nth(i).evaluate(
                "el => getComputedStyle(el).getPropertyValue('--heat') || '0'") or 0)
            if heat > best:
                hottest, best = cells.nth(i), heat
        if hottest is not None:
            hottest.click()
        page.get_by_role("button", name="Text").click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SCREENS / "workspace.png"))
        browser.close()
    print(f"[+] {SCREENS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
