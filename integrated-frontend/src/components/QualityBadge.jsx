/**
 * What the evaluator made of a generated resource.
 *
 * Everything this system generates is graded by a second model -- a different family from
 * the generator, so it does not just rate its own writing style highly -- and content that
 * scored below the threshold is stored and shown anyway, flagged. That is the honest
 * behaviour: a student waiting on a quiz is better served by flagged output than by
 * nothing, and hiding rejections would make the failure rate invisible.
 *
 * qualityTone() is exported separately so the compact list badges in ResourcesPanel and
 * resources/index.jsx can share this exact judgment rather than each hand-rolling their
 * own slightly different copy of it.
 */

export function qualityTone({ accepted, score } = {}) {
  const unevaluated = score === null || score === undefined;
  if (unevaluated) return { tone: "bg-gray-100 text-muted", label: "Not reviewed" };
  if (accepted) return { tone: "bg-verified-bg text-verified", label: `Reviewed · ${score}/100` };
  return { tone: "bg-pending-bg text-pending", label: `Flagged · ${score}/100` };
}

function QualityBadge({ resource, className = "" }) {
  const { accepted, score, threshold, n_attempts: attempts, reasoning } = resource || {};
  const unevaluated = score === null || score === undefined;
  const { tone, label } = qualityTone(resource);

  return (
    <div className={className}>
      <span className={`inline-block text-xs rounded-full px-2.5 py-1 font-medium ${tone}`}>
        {label}
        {!unevaluated && threshold ? ` (pass ${threshold})` : ""}
        {attempts > 1 ? ` · ${attempts} attempts` : ""}
      </span>

      {unevaluated && (
        <p className="text-xs text-muted mt-1">
          Generated with evaluation switched off — nothing has checked this against the
          document.
        </p>
      )}

      {!unevaluated && !accepted && (
        <p className="text-xs text-pending mt-1">
          This scored below the pass mark and is shown anyway. Check it against the document
          before relying on it.
        </p>
      )}

      {reasoning && (
        <details className="text-xs text-muted mt-1">
          <summary className="cursor-pointer">What the evaluator said</summary>
          <p className="mt-1 whitespace-pre-wrap">{reasoning}</p>
        </details>
      )}
    </div>
  );
}

export default QualityBadge;
