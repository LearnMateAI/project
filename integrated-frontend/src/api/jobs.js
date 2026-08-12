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
 * How often to ask. The work takes minutes, so this is nowhere near a load concern -- it
 * is set by how often `progress.message` changes, which is roughly per page summarised or
 * per generation attempt. Slower than this and the commentary looks stuck.
 */
const POLL_INTERVAL_MS = 1500;

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

    await sleep(POLL_INTERVAL_MS, signal);
  }
}
