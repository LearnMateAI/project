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
    return (
      <div className={`text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2 ${className}`}>
        {job.error}
      </div>
    );
  }

  if (!job.isRunning) return null;

  const { message, current, total } = job.progress || {};
  const percent = total ? Math.min(100, Math.round((current / total) * 100)) : null;

  return (
    <div className={`text-sm text-gray-600 ${className}`}>
      <p className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
        {message || "Working..."}
      </p>
      {percent !== null && (
        <div className="mt-2 w-full bg-gray-200 rounded h-2">
          <div className="bg-blue-600 h-2 rounded transition-all" style={{ width: `${percent}%` }} />
        </div>
      )}
    </div>
  );
}

export default JobProgress;
