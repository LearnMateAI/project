/**
 * Background jobs: the mechanism the rest of this app is shaped around.
 *
 * Uploading, generating and chatting all return `202 {job_id}` rather than a result,
 * because on the local models they take 30 seconds to several minutes -- no browser holds
 * a connection that long and no proxy allows it. So every one of those calls is really:
 *
 *     POST something        -> {job_id}
 *     waitForJob(job_id)    -> the result, eventually
 *
 * `waitForJob` is the whole of it. React components use the useJob hook rather than
 * calling this directly; it is exported because a non-React caller (a script, a test)
 * should not have to.
 */

import api from "./client.js";

/**
 * How often to ask, and why it changes partway through.
 *
 * A whole-document generation runs for minutes and its commentary changes about once per
 * page summarised or per generation attempt, so 1.5s is the right rhythm for it -- slower
 * and the progress line looks stuck.
 *
 * A small ingest is a different job entirely: about a second of real work once the server
 * is warm. Against a flat 1.5s poll the user spends longer waiting to be told than the
 * work took. So the opening seconds are polled fast, and it backs off to the slow rhythm
 * for the long runs that need it. Neither rate is a load concern -- this is one reader
 * asking about one job.
 */
const FAST_POLL_MS = 300;
const SLOW_POLL_MS = 1500;
const FAST_POLL_FOR_MS = 5000;

export function getJob(jobId) {
  return api.get(`/api/jobs/${jobId}`);
}

export function listJobs(params = {}) {
  return api.get("/api/jobs", { params });
}

const sleep = (ms, signal) =>
  new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });

/**
 * Poll one job to completion.
 *
 * Resolves with the job's `result` -- the same object the endpoint would have returned if
 * it could have waited. Throws with the backend's `error` message on failure, and with an
 * AbortError when `signal` fires, so a component that unmounts mid-generation stops
 * polling instead of setting state on a dead tree.
 *
 * There is no timeout here on purpose: a whole-document run legitimately takes many
 * minutes, and a client-side cutoff would report a failure for something that is still
 * working perfectly well. The caller can pass a signal if it wants to give up.
 */
export async function waitForJob(jobId, { onProgress, signal } = {}) {
  let lastMessage;
  const startedAt = Date.now();

  for (;;) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

    const { data: job } = await getJob(jobId);

    const message = job.progress?.message;
    // Only fire on change: the same string arriving forty times is not progress, and
    // re-rendering on each poll makes the UI flicker.
    if (onProgress && message && message !== lastMessage) {
      lastMessage = message;
      onProgress(job.progress, job);
    }

    if (job.status === "done") return job.result;
    if (job.status === "failed") {
      throw new Error(job.error || "The job failed.");
    }

    const elapsed = Date.now() - startedAt;
    await sleep(elapsed < FAST_POLL_FOR_MS ? FAST_POLL_MS : SLOW_POLL_MS, signal);
  }
}
