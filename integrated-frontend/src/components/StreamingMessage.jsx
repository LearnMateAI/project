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
      <div className="bg-white border rounded-lg px-4 py-3 max-w-[85%] shadow-sm">
        {text ? (
          <>
            <div className="whitespace-pre-wrap text-gray-800">
              {text}
              {/* Sits on the last line rather than below it, so the answer reads as
                  still being typed rather than as finished with something after it. */}
              <span className="inline-block w-1.5 h-4 ml-0.5 -mb-0.5 bg-gray-400 animate-pulse" />
            </div>
            {/* Once text is flowing the commentary is demoted: the answer is the thing
                being watched, and "Generating (attempt 2/2)..." still matters because it
                is the only signal that a regeneration has started over. */}
            {message && <p className="text-xs text-gray-400 mt-2">{message}</p>}
          </>
        ) : (
          <p className="flex items-center gap-2 text-sm text-gray-500">
            <span className="inline-block w-3 h-3 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
            {message || "Working..."}
          </p>
        )}
      </div>
    </div>
  );
}

export default StreamingMessage;
