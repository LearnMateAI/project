/**
 * The reply as it is being written, before the turn exists.
 *
 * Shaped to match the assistant bubble in ChatMessage so that when the job finishes and
 * the real turn replaces this one, the text does not jump. What it deliberately does
 * *not* show is the audit trail -- mode, score, pages -- because none of that is known
 * yet: the mode is settled, but the score does not exist until the judge has run, and a
 * badge that appears and then changes its mind is worse than one that waits.
 *
 * Three states, not two, and the middle one is the point:
 *
 *   no text yet   a spinner and whatever the backend is doing ("Retrieving...")
 *   writing       the text so far, with a cursor on the last line
 *   reply_ready   the finished answer, cursor gone, with a quiet note that it is being
 *                 checked -- because the judge takes longer than the writing did, and a
 *                 reader who already has the answer should not be made to watch a cursor
 *                 blink through it. See app/jobs/runners.py, which publishes the milestone.
 *
 * The text cannot change under the reader once reply_ready is up: a regeneration is not
 * streamed over it. If the retry scores better, the finished turn swaps it in, once.
 */

function StreamingMessage({ progress }) {
  const { message, partial, reply_ready: replyReady } = progress || {};
  const text = (partial || "").trim();

  return (
    <div className="flex justify-start">
      <div className="bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-3.5 max-w-[85%] shadow-card">
        {text ? (
          <>
            <div className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-body">
              {text}
              {/* Sits on the last line rather than below it, so the answer reads as
                  still being typed rather than as finished with something after it.
                  Dropped once the reply is whole: a cursor on a finished answer is
                  exactly what keeps a reader waiting for more of it. */}
              {!replyReady && (
                <span className="inline-block w-1.5 h-4 ml-0.5 -mb-0.5 bg-primary animate-pulse rounded-sm" />
              )}
            </div>
            {replyReady ? (
              /* The answer is readable now, so this only explains why the turn has not
                 closed yet. Deliberately quiet -- a footnote, not a status anybody is
                 waiting on. */
              <p className="flex items-center gap-2 text-[11.5px] text-subtle mt-2 m-0">
                <span className="spinner" />
                {message || "Checking this answer..."}
              </p>
            ) : (
              /* Once text is flowing the commentary is demoted: the answer is the thing
                 being watched, and the line below it only says which stage is running.
                 The attempt counter is stripped before it gets here -- see the reporter in
                 app/jobs/runners.py -- so a regeneration reads as "Generating..." again
                 rather than advertising that the last one was rejected. */
              message && <p className="text-[11.5px] text-subtle mt-2">{message}</p>
            )}
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
