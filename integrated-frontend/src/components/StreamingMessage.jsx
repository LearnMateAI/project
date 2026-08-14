/**
 * The reply as it is being written, before the turn exists.
 *
 * Shaped to match the assistant bubble in ChatMessage so that when the job finishes and
 * the real turn replaces this one, the text does not jump. What it deliberately does
 * *not* show is the audit trail -- mode, score, pages -- because none of that is known
 * yet: the mode is settled, but the score does not exist until the judge has run, and a
 * badge that appears and then changes its mind is worse than one that waits.
 *
 * Falls back to the job's commentary ("Evaluating...") whenever there is no text to show,
 * which covers the seconds before the first token and the pause while the judge grades.
 */

function StreamingMessage({ progress }) {
  const { message, partial } = progress || {};
  const text = (partial || "").trim();

  return (
    <div className="flex justify-start">
      <div className="bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-3.5 max-w-[85%] shadow-card">
        {text ? (
          <>
            <div className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-body">
              {text}
              {/* Sits on the last line rather than below it, so the answer reads as
                  still being typed rather than as finished with something after it. */}
              <span className="inline-block w-1.5 h-4 ml-0.5 -mb-0.5 bg-primary animate-pulse rounded-sm" />
            </div>
            {/* Once text is flowing the commentary is demoted: the answer is the thing
                being watched, and "Generating (attempt 2/2)..." still matters because it
                is the only signal that a regeneration has started over. */}
            {message && <p className="text-[11.5px] text-subtle mt-2">{message}</p>}
          </>
        ) : (
          <p className="flex items-center gap-2.5 text-[13px] text-muted m-0">
            <span className="spinner" />
            {message || "Working..."}
          </p>
        )}
      </div>
    </div>
  );
}

export default StreamingMessage;
