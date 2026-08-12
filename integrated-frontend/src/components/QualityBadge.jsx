/**
 * What the evaluator made of a generated resource.
 *
 * Everything this system generates is graded by a second model -- a different family from
 * the generator, so it does not just rate its own writing style highly -- and content that
 * scored below the threshold is stored and shown anyway, flagged. That is the honest
 * behaviour: a student waiting on a quiz is better served by flagged output than by
 * nothing, and hiding rejections would make the failure rate invisible.
 *
 * So this badge always says which happened. `score` is null when evaluation was switched
 * off for that run, which is a third state and not the same as passing.
 */

function QualityBadge({ resource, className = "" }) {
  const { accepted, score, threshold, n_attempts: attempts, reasoning } = resource || {};

  const unevaluated = score === null || score === undefined;

  const tone = unevaluated
    ? "bg-gray-100 text-gray-600 border-gray-200"
    : accepted
      ? "bg-green-50 text-green-700 border-green-200"
      : "bg-amber-50 text-amber-700 border-amber-200";

  const label = unevaluated
    ? "Not reviewed"
    : accepted
      ? `Reviewed · ${score}/100`
      : `Flagged · ${score}/100`;

  return (
    <div className={className}>
      <span className={`inline-block text-xs border rounded px-2 py-1 ${tone}`}>
        {label}
        {!unevaluated && threshold ? ` (pass ${threshold})` : ""}
        {attempts > 1 ? ` · ${attempts} attempts` : ""}
      </span>

      {unevaluated && (
        <p className="text-xs text-gray-500 mt-1">
          Generated with evaluation switched off — nothing has checked this against the
          document.
        </p>
      )}

      {!unevaluated && !accepted && (
        <p className="text-xs text-amber-700 mt-1">
          This scored below the pass mark and is shown anyway. Check it against the document
          before relying on it.
        </p>
      )}

      {reasoning && (
        <details className="text-xs text-gray-500 mt-1">
          <summary className="cursor-pointer">What the evaluator said</summary>
          <p className="mt-1 whitespace-pre-wrap">{reasoning}</p>
        </details>
      )}
    </div>
  );
}

export default QualityBadge;
