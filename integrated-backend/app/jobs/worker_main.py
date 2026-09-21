"""
A worker process: takes jobs from the MongoDB lease queue, serves no HTTP.

    python -m app.jobs.worker_main --workers 4
    python -m app.jobs.worker_main --workers 8 --kinds chat --name mac-gpu

Run as many as the model servers can feed, on as many machines as can reach the database
and Qdrant. Each claims jobs atomically, renews its leases while it works, and on Ctrl+C
stops taking new work and gives running jobs a grace period; a job it abandons anyway is
requeued by whichever reaper next sees its lease lapse.

Requires JOB_QUEUE_BACKEND=mongo -- an in-memory queue in another process is invisible
from here. Set JOB_RUN_IN_API=0 on the API server to leave all the work to these.
"""

import argparse
import logging
import signal
import threading

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger("learnmate.worker_main")


def main(argv=None) -> int:
    from .. import config
    from . import worker

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workers", type=int, default=config.JOB_WORKERS)
    parser.add_argument("--kinds", default=",".join(config.JOB_KINDS),
                        help="comma-separated job kinds to take (ingest,resource,chat)")
    parser.add_argument("--name", default=None, help="worker id prefix, for the logs")
    parser.add_argument("--grace", type=float, default=30.0,
                        help="seconds running jobs get to finish on shutdown")
    args = parser.parse_args(argv)

    if config.JOB_QUEUE_BACKEND != "mongo":
        logger.error("JOB_QUEUE_BACKEND is %r; a separate worker process needs 'mongo'.",
                     config.JOB_QUEUE_BACKEND)
        return 2

    from learnmate.storage import ensure_indexes

    ensure_indexes()
    worker.warm_up()
    kinds = [kind.strip() for kind in args.kinds.split(",") if kind.strip()]
    started = worker.start_workers(args.workers, kinds=kinds, name=args.name)
    logger.info("worker_main running %d worker(s) for %s. Ctrl+C to stop.", started, kinds)

    stop = threading.Event()

    def _signal(signum, _frame):
        logger.info("Signal %s: draining (up to %.0fs)...", signum, args.grace)
        stop.set()

    signal.signal(signal.SIGINT, _signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal)

    while not stop.wait(1.0):
        pass
    worker.shutdown(timeout=args.grace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
