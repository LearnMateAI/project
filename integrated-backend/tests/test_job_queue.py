"""
Unit tests for the scalable job queue (app/jobs, learnmate/storage/jobs) and the served-model
client (learnmate/llm/http_api).

Model-free and, except for one opt-in test, Mongo-free. The opt-in test runs real claims
against a real MongoDB when LEARNMATE_TEST_MONGO_URI is set, e.g.

    set LEARNMATE_TEST_MONGO_URI=mongodb://localhost:27018
    python -m unittest tests.test_job_queue
"""

from __future__ import annotations

import os
import threading
import time
import unittest
from unittest import mock

import requests

from app.jobs import queue as job_queue
from app.jobs import worker
from learnmate.llm.http_api import HttpChatModel
from learnmate.storage import jobs as job_store


class WorkerCountTests(unittest.TestCase):
    def test_in_process_models_force_one_worker(self):
        count, reason = worker.effective_worker_count(4, "llamacpp", "http")
        self.assertEqual(count, 1)
        self.assertIn("generator", reason)

    def test_served_models_allow_a_pool(self):
        self.assertEqual(worker.effective_worker_count(4, "http", "http"), (4, None))

    def test_one_is_always_fine(self):
        self.assertEqual(worker.effective_worker_count(1, "llamacpp", "llamacpp"), (1, None))


class QueueBackendTests(unittest.TestCase):
    def test_memory_queue_hands_over_and_starts_the_job(self):
        backend = job_queue.MemoryQueue()
        backend.put("j1")
        with mock.patch.object(job_store, "get", return_value={"_id": "j1"}), \
                mock.patch.object(job_store, "start") as start:
            job = backend.take("w", timeout=0.1)
        self.assertEqual(job, {"_id": "j1"})
        start.assert_called_once_with("j1")
        backend.wake_all(1)
        self.assertIs(backend.take("w", timeout=0.1), job_queue.SHUTDOWN)

    def test_lease_queue_claims_and_wakes_for_shutdown(self):
        backend = job_queue.MongoLeaseQueue(["chat"], lease_s=30, poll_s=0.05)
        with mock.patch.object(job_store, "claim", return_value={"_id": "j2"}) as claim:
            self.assertEqual(backend.take("w-0", timeout=1), {"_id": "j2"})
        claim.assert_called_once_with("w-0", ["chat"], 30)
        with mock.patch.object(job_store, "claim", return_value=None):
            self.assertIsNone(backend.take("w-0", timeout=1))
            backend.wake_all(1)
            self.assertIs(backend.take("w-0", timeout=1), job_queue.SHUTDOWN)

    def test_lease_queue_startup_does_not_fail_other_workers_jobs(self):
        backend = job_queue.MongoLeaseQueue(["chat"], 30, 0.5)
        with mock.patch.object(job_store, "fail_legacy_orphans", return_value=0) as orphans, \
                mock.patch.object(job_store, "fail_running") as fail_running:
            backend.startup()
        orphans.assert_called_once()
        fail_running.assert_not_called()


class ExecuteTests(unittest.TestCase):
    def test_success_writes_result_under_the_lease(self):
        with mock.patch("app.jobs.runners.run", return_value={"ok": 1}), \
                mock.patch.object(job_store, "heartbeat", return_value=True), \
                mock.patch.object(job_store, "finish", return_value=True) as finish:
            worker._execute({"_id": "abc123", "kind": "chat"}, worker_id="w-0")
        finish.assert_called_once_with("abc123", {"ok": 1}, worker_id="w-0")

    def test_failure_is_recorded_under_the_lease(self):
        with mock.patch("app.jobs.runners.run", side_effect=ValueError("unknown model_id")), \
                mock.patch.object(job_store, "heartbeat", return_value=True), \
                mock.patch.object(job_store, "fail") as fail:
            worker._execute({"_id": "abc123", "kind": "chat"}, worker_id="w-0")
        args, kwargs = fail.call_args
        self.assertEqual(args[2], "model")
        self.assertEqual(kwargs["worker_id"], "w-0")

    def test_lost_lease_drops_the_result(self):
        def slow_run(_job):
            time.sleep(0.3)
            return {"late": True}

        with mock.patch("app.jobs.runners.run", side_effect=slow_run), \
                mock.patch.object(job_store, "heartbeat", return_value=False), \
                mock.patch.object(worker.config, "JOB_HEARTBEAT_S", 0.05), \
                mock.patch.object(job_store, "finish") as finish:
            worker._execute({"_id": "abc123", "kind": "chat"}, worker_id="w-0")
        finish.assert_not_called()


class _FakeResponse:
    def __init__(self, status, content='{"score": 80}'):
        self.status_code = status
        self._content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class HttpSchemaFallbackTests(unittest.TestCase):
    def _model(self):
        return HttpChatModel(base_url="http://server/v1", model_name="m")

    def _run(self, first_status):
        calls = []

        def post(url, json=None, headers=None, timeout=None, **_):
            calls.append(json)
            return _FakeResponse(first_status if len(calls) == 1 else 200)

        session = mock.Mock()
        session.post.side_effect = post
        with mock.patch("learnmate.llm.http_api._session", return_value=session):
            try:
                self._model().invoke("hi", response_schema={"type": "object"})
            except requests.HTTPError:
                pass
        return calls

    def test_schema_rejection_falls_back_to_plain(self):
        calls = self._run(400)
        self.assertEqual(len(calls), 2)
        self.assertIn("response_format", calls[0])
        self.assertNotIn("response_format", calls[1])

    def test_server_error_is_not_retried_unconstrained(self):
        calls = self._run(503)
        self.assertEqual(len(calls), 1)

    def test_schema_is_sent_openai_style(self):
        calls = self._run(200)
        fmt = calls[0]["response_format"]
        self.assertEqual(fmt["type"], "json_schema")
        self.assertEqual(fmt["json_schema"]["schema"], {"type": "object"})


@unittest.skipUnless(os.getenv("LEARNMATE_TEST_MONGO_URI"), "needs a MongoDB")
class RealMongoLeaseTests(unittest.TestCase):
    """Claims against a real server: each job exactly once, lapsed leases come back."""

    def setUp(self):
        from pymongo import MongoClient

        from learnmate import config
        from learnmate.storage.indexes import create_indexes

        self.client = MongoClient(os.environ["LEARNMATE_TEST_MONGO_URI"])
        self.db = self.client[f"learnmate_test_{os.getpid()}"]
        create_indexes(self.db)
        self.patch = mock.patch.object(job_store, "_collection",
                                       return_value=self.db[config.COLL_JOBS])
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.client.drop_database(self.db.name)

    def test_concurrent_claims_take_each_job_once(self):
        ids = {str(job_store.create("u", "chat", {"i": i}, max_attempts=2)["_id"])
               for i in range(60)}
        claimed, lock = [], threading.Lock()

        def drain(name):
            while True:
                job = job_store.claim(name, ["chat"], lease_s=30)
                if job is None:
                    return
                with lock:
                    claimed.append(str(job["_id"]))

        threads = [threading.Thread(target=drain, args=(f"w{i}",)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(claimed), sorted(ids))

    def test_lapsed_lease_is_requeued_then_failed_when_spent(self):
        job_id = job_store.create("u", "chat", {}, max_attempts=2)["_id"]
        self.assertIsNotNone(job_store.claim("dead", ["chat"], lease_s=0.01))
        time.sleep(0.05)
        self.assertEqual(job_store.requeue_expired(0), (1, 0))
        self.assertIsNotNone(job_store.claim("dead-again", ["chat"], lease_s=0.01))
        time.sleep(0.05)
        self.assertEqual(job_store.requeue_expired(0), (0, 1))
        self.assertEqual(job_store.get(job_id)["status"], job_store.FAILED)

    def test_only_the_lease_holder_can_finish(self):
        job_id = job_store.create("u", "chat", {})["_id"]
        job_store.claim("owner", ["chat"], lease_s=30)
        self.assertFalse(job_store.finish(job_id, {"x": 1}, worker_id="impostor"))
        self.assertTrue(job_store.heartbeat(job_id, "owner", 30))
        self.assertTrue(job_store.finish(job_id, {"x": 1}, worker_id="owner"))


if __name__ == "__main__":
    unittest.main()
