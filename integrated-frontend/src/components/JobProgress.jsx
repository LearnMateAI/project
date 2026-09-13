/**
 * What a running job is doing, from a useJob() result.
 *
 * The backend writes real commentary onto the job record -- "Summarising page 4 (4/7)...",
 * "Group 2/5: Generating mcq (attempt 1/2)...", "Embedding 1240 chunks into Qdrant..." --
 * so this shows that text rather than a spinner. During a five-minute generation the
 * difference between the two is whether the user can tell it is working.
 *
 * The bar only appears when the backend gave a total; most jobs report a message and no
 * numbers, and an indeterminate bar pretending to be a determinate one is worse than none.
 */

function JobProgress({ job, className = "" }) {
  if (job.status === "idle") return null;

  if (job.isFailed) {
    return <div className={`notice notice-error ${className}`}>{job.error}</div>;
  }

  if (!job.isRunning) return null;

  const { message, current, total, jobStatus } = job.progress || {};
  const percent = total ? Math.min(100, Math.round((current / total) * 100)) : null;
  const waitingForServer = jobStatus === "queued" || /^waiting/i.test(message || "");

  return (
    <div className={`rounded-xl bg-primary-soft border border-primary-light px-3.5 py-3 ${className}`}>
      <p className="flex items-center gap-2.5 text-[13px] font-medium text-primary-dark m-0">
        {waitingForServer ? <span className="spinner" /> : null}
        {message || (waitingForServer ? "Waiting for the server..." : "Working...")}
      </p>
      {!waitingForServer && (
        <p className="text-[11.5px] text-muted m-0 mt-1 leading-relaxed">
          Job running in the background — safe to navigate away.
        </p>
      )}
      {percent !== null && (
        <div className="track mt-2.5">
          <span style={{ width: `${percent}%` }} />
        </div>
      )}
    </div>
  );
}

export default JobProgress;
