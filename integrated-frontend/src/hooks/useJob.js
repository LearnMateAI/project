/**
 * Running one background job from a component.
 *
 *     const job = useJob();
 *     await job.run(() => generateResource({ documentId, resourceType: "mcq" }));
 *
 * `run` takes a function that returns the 202 response, reads `job_id` off it, and polls
 * until the job finishes -- exposing `status`, the backend's own `progress.message`, and
 * finally `result` or `error`.
 *
 * Three things this handles that a bare `await waitForJob(...)` in a component does not:
 *
 *   - it aborts on unmount, so navigating away mid-generation stops the polling instead of
 *     setting state on a tree that no longer exists;
 *   - it surfaces `progress.message` as it changes, which is the difference between a
 *     spinner and "Group 2/5: Generating mcq (attempt 1/2)..." during a five-minute run;
 *   - it returns the result *and* stores it, so a caller can either await it or render it.
 *
 * `run` resolves with the result and re-throws nothing -- failures land in `error`. A
 * caller that wants to branch checks the resolved value, which is `undefined` on failure.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client.js";
import { waitForJob } from "../api/jobs.js";

const IDLE = "idle";
const RUNNING = "running";
const DONE = "done";
const FAILED = "failed";

export function useJob() {
  const [status, setStatus] = useState(IDLE);
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  // One controller per hook instance, replaced on each run and aborted on unmount.
  const controllerRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  const reset = useCallback(() => {
    setStatus(IDLE);
    setProgress(null);
    setResult(null);
    setError("");
  }, []);

  const run = useCallback(async (start) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setStatus(RUNNING);
    setProgress({ message: "Starting..." });
    setResult(null);
    setError("");

    try {
      const response = await start();
      const jobId = response?.data?.job_id;
      if (!jobId) throw new Error("The server did not return a job id.");

      const jobResult = await waitForJob(jobId, {
        signal: controller.signal,
        onProgress: (next) => {
          if (mountedRef.current) setProgress(next);
        },
      });

      if (!mountedRef.current) return undefined;
      setResult(jobResult);
      setStatus(DONE);
      return jobResult;
    } catch (exc) {
      // An abort is this component going away, not a failure worth reporting.
      if (exc?.name === "AbortError" || !mountedRef.current) return undefined;
      setError(errorMessage(exc, exc?.message));
      setStatus(FAILED);
      return undefined;
    }
  }, []);

  return {
    run,
    reset,
    status,
    progress,
    result,
    error,
    isRunning: status === RUNNING,
    isDone: status === DONE,
    isFailed: status === FAILED,
  };
}
