"""
Throughput and tail latency under concurrent students, against a running API server.

    python -m eval.load_test --base-url http://localhost:8010 --users 1 2 4 8 \
        --duration 300 --label pool_cache

A closed-loop load generator in plain threads (no Locust: nothing to install, and the
numbers are the same shape). Each simulated student is a real account: it registers, uploads
the same chapter (instantly -- the server de-duplicates by content hash), opens a session,
and then loops: ask a question, poll the job until it is done, think for a few seconds, ask
again. Questions are drawn Zipf-style from the workload's families for that chapter, in a
random wording, as the session log does.

Measured per ask:
    e2e       POST to job done -- what the student waits for in full
    ttr       POST to the first poll showing the reply (reply_ready or done) -- what the
              student waits for before they can read
    wait      queue time: job started_at - created_at, from the job record
    cache     whether the answer was reused

Reported per concurrency level over the steady window (the first `--warmup` seconds are
dropped): completed chats per minute, and p50/p95 of e2e and ttr. The server's own
configuration -- queue backend, workers, retrieval, cache -- is read from /api/health and
stored with the result, so a run is labelled by what was actually running.

Server configurations compared in the paper (set in the server's environment):
    baseline     JOB_QUEUE_BACKEND=memory, in-process llama.cpp (one worker)
    pool         JOB_QUEUE_BACKEND=mongo JOB_WORKERS=4, llama-server with 4 slots per model
    pool_cache   pool + LEARNMATE_CACHE_ENABLED=1
"""

import argparse
import json
import random
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

from eval.common import CORPUS_DIR, WORKLOAD_DIR, provenance, read_jsonl, run_dir, write_json
from eval.metrics import latency_summary


class Student:
    def __init__(self, base_url: str, index: int, label: str):
        self.base = base_url.rstrip("/")
        self.http = requests.Session()
        self.name = f"load-{label}-{index}-{uuid.uuid4().hex[:6]}"

    def _post(self, path, **kwargs):
        response = self.http.post(f"{self.base}{path}", timeout=120, **kwargs)
        response.raise_for_status()
        return response.json()

    def _get(self, path, **kwargs):
        response = self.http.get(f"{self.base}{path}", timeout=60, **kwargs)
        response.raise_for_status()
        return response.json()

    def provision(self, pdf: Path) -> None:
        auth = self._post("/api/auth/register",
                          json={"name": self.name, "email": f"{self.name}@example.com",
                                "password": "Eval-password-123"})
        self.http.headers["Authorization"] = f"Bearer {auth['token']}"
        with pdf.open("rb") as handle:
            upload = self._post("/api/documents", files={"file": (pdf.name, handle,
                                                                   "application/pdf")})
        self.wait(upload["job_id"], timeout=1800)
        document_id = upload["document"]["id"]
        self.session = self._post("/api/chat/sessions",
                                  json={"document_id": document_id})["session_id"]

    def wait(self, job_id: str, timeout: float, poll: float = 0.5):
        started = time.perf_counter()
        ready_at = None
        while time.perf_counter() - started < timeout:
            job = self._get(f"/api/jobs/{job_id}", params={"minimal": "true"})
            progress = job.get("progress") or {}
            if ready_at is None and (progress.get("reply_ready") or job["status"] == "done"):
                ready_at = time.perf_counter()
            if job["status"] in ("done", "failed"):
                return job, ready_at
            time.sleep(poll)
        raise TimeoutError(job_id)

    def ask(self, text: str):
        started = time.perf_counter()
        job_id = self._post(f"/api/chat/sessions/{self.session}/messages",
                            json={"message": text})["job_id"]
        job, ready_at = self.wait(job_id, timeout=1800)
        finished = time.perf_counter()
        full = self._get(f"/api/jobs/{job_id}")
        result = full.get("result") or {}

        def parse(value):
            return datetime.fromisoformat(value) if value else None

        created, begun = parse(full.get("created_at")), parse(full.get("started_at"))
        return {"status": job["status"], "e2e_ms": (finished - started) * 1000,
                "ttr_ms": ((ready_at or finished) - started) * 1000,
                "wait_ms": ((begun - created).total_seconds() * 1000
                            if created and begun else None),
                "cache_hit": bool((result.get("cache") or {}).get("hit")),
                "mode": result.get("mode"), "finished_at": finished}


def run_level(base_url, users, duration, warmup, think, pdf, pool, label, seed):
    rng = random.Random(seed + users)
    students = [Student(base_url, i, f"{label}-{users}") for i in range(users)]
    print(f"[*] {users} users: provisioning...")
    for student in students:
        student.provision(pdf)

    records, lock = [], threading.Lock()
    start = time.perf_counter()
    stop_at = start + duration

    def loop(student, local_seed):
        local = random.Random(local_seed)
        time.sleep(local.uniform(0, think[1]))      # stagger the first asks
        while time.perf_counter() < stop_at:
            text = local.choices(pool, weights=[w for _, w in pool_weights])[0]
            try:
                record = student.ask(text)
            except Exception as exc:
                record = {"status": "error", "error": str(exc),
                          "finished_at": time.perf_counter()}
            record["t"] = record["finished_at"] - start
            with lock:
                records.append(record)
            time.sleep(local.uniform(*think))

    pool_weights = [(text, 1.0 / (rank + 1) ** 1.1) for rank, text in enumerate(pool)]
    threads = [threading.Thread(target=loop, args=(s, rng.random()), daemon=True)
               for s in students]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=duration + 1800)

    steady = [r for r in records if r["t"] >= warmup and r["status"] == "done"]
    window_min = max(1e-9, (duration - warmup) / 60.0)
    return {
        "users": users,
        "completed": len(steady),
        "errors": sum(r["status"] != "done" for r in records),
        "throughput_per_min": len(steady) / window_min,
        "e2e_ms": latency_summary([r["e2e_ms"] for r in steady]),
        "ttr_ms": latency_summary([r["ttr_ms"] for r in steady]),
        "queue_wait_ms": latency_summary([r["wait_ms"] for r in steady
                                          if r.get("wait_ms") is not None]),
        "cache_hit_rate": (sum(r["cache_hit"] for r in steady) / len(steady)
                           if steady else None),
        "records": records,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--users", nargs="+", type=int, default=[1, 2, 4, 8])
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--think", nargs=2, type=float, default=[3.0, 8.0])
    parser.add_argument("--chapter", type=int, default=7)
    parser.add_argument("--label", default="run")
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)

    manifest = json.loads((CORPUS_DIR / "corpus.json").read_text(encoding="utf-8"))
    entry = next(d for d in manifest["documents"] if d["chapter"] == args.chapter)
    pdf = CORPUS_DIR / "docs" / entry["filename"]
    pool = [q["text"] for q in read_jsonl(WORKLOAD_DIR / "questions.jsonl")
            if q["chapter"] == args.chapter and q["variant"] in ("seed", "para")]
    random.Random(args.seed).shuffle(pool)

    health = requests.get(f"{args.base_url.rstrip('/')}/api/health", timeout=30).json()
    levels = [run_level(args.base_url, users, args.duration, args.warmup, args.think, pdf,
                        pool, args.label, args.seed) for users in args.users]
    for level in levels:
        print(f"  {level['users']:3d} users: {level['throughput_per_min']:.2f} chats/min, "
              f"e2e p50 {level['e2e_ms']['p50']}, p95 {level['e2e_ms']['p95']}, "
              f"hit rate {level['cache_hit_rate']}")
    path = write_json(run_dir("load") / f"load_{args.label}.json",
                      {"label": args.label, "server": health, "levels": levels,
                       "duration_s": args.duration, "warmup_s": args.warmup,
                       "think_s": args.think, "chapter": args.chapter,
                       "provenance": provenance()})
    print(f"[+] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
