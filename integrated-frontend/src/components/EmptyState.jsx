/**
 * A one-line empty state with an optional call to action.
 *
 * Used on Documents, Resources and Chat before the user has created anything, so a blank
 * card is replaced by a sentence that says what to do next.
 */

function EmptyState({ title, body, action, className = "" }) {
  return (
    <div className={`text-center px-5 py-8 ${className}`}>
      {title ? <p className="text-[14px] font-semibold text-heading m-0">{title}</p> : null}
      <p className={`text-[13px] text-muted m-0 leading-relaxed ${title ? "mt-1" : ""}`}>
        {body}
      </p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export default EmptyState;
