/**
 * What a running job is doing, from a useJob() result.
 *
 * The backend writes real commentary onto the job record -- "Summarising page 4 (4/7)...",
 * "Group 2/5: Generating mcq (attempt 1/2)...", "Embedding 1240 chunks into Qdrant..." --
 * so this shows that text rather than a spinner.
 */

function JobProgress({ job, className = "" }) {
  if (job.status === "idle") return null;

  if (job.isFailed) {
    return (
      <div className={`text-sm text-danger bg-danger-bg rounded-lg p-3 ${className}`}>
        {job.error}
      </div>
    );
  }

  if (!job.isRunning) return null;

  const { message, current, total } = job.progress || {};
  const percent = total ? Math.min(100, Math.round((current / total) * 100)) : null;

  return (
    <div className={`text-sm text-muted ${className}`}>
      <p className="flex items-center gap-2">
        <span className="inline-block w-3 h-3 rounded-full border-2 border-ink border-t-transparent animate-spin" />
        {message || "Working..."}
      </p>
      {percent !== null && (
        <div className="mt-2 w-full bg-gray-100 rounded-full h-2">
          <div className="bg-ink h-2 rounded-full transition-all" style={{ width: `${percent}%` }} />
        </div>
      )}
    </div>
  );
}

export default JobProgress;
