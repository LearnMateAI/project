/**
 * One turn in a conversation.
 *
 * A user turn is just text. An assistant turn carries what the answer was built from:
 *
 *   pages     which pages it drew on, with the retrieved text behind a disclosure, so the
 *             answer can be checked against the source rather than trusted.
 *   attempts  shown only when the reply needed regenerating.
 *
 * The evaluator's score and the pdf/general mode badge used to sit above the text and no
 * longer do. The warning below the reply stays: a score is a number a reader cannot act
 * on, whereas "check this against the document" is an instruction they can.
 *
 * The same fields arrive on a live reply and on a turn replayed from history, so a resumed
 * conversation looks identical to one still in progress.
 */

function ChatMessage({ turn }) {
  const isUser = turn.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="bg-primary text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] whitespace-pre-wrap text-[13.5px] leading-relaxed shadow-[0_6px_16px_-8px_rgba(35,64,224,0.6)]">
          {turn.content}
        </div>
      </div>
    );
  }

  const pages = (turn.pages || []).filter((page) => page !== null && page !== undefined);
  const uniquePages = [...new Set(pages)].sort((a, b) => a - b);
  const flagged = turn.accepted === false && turn.score !== null && turn.score !== undefined;

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-3.5 max-w-[85%] shadow-card">
        {/* The row only exists when there is something to put in it -- rendered
            unconditionally it would leave an empty strip of margin above the reply. */}
        {turn.attempts > 1 && (
          <div className="flex flex-wrap items-center gap-2 mb-2.5">
            <span className="text-[11.5px] text-subtle">{turn.attempts} attempts</span>
          </div>
        )}

        {/* Shown only when the rewrite actually changed the question. On a follow-up like
            "what about his powers?" the retrieval is only as good as this line, so a bad
            answer is usually a bad rewrite -- and invisible without it. */}
        {turn.standalone_query && turn.standalone_query !== turn.query && (
          <p className="text-[11.5px] text-muted italic mb-2 border-l-2 border-border pl-2.5">
            Searched for: {turn.standalone_query}
          </p>
        )}

        <div className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-body">{turn.content}</div>

        {flagged && (
          <p className="text-[12px] text-warning mt-2.5">
            This scored below the pass mark. Check it against the document.
          </p>
        )}

        {/* Numbered footnote chips, one per source page -- echoing how a citation would be
            marked in the text itself, rather than a plain "From pages ..." caption. */}
        {uniquePages.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            {uniquePages.map((page, i) => (
              <span key={page} className="footnote-chip">
                <span className="footnote-mark">{i + 1}</span>
                p. {page}
              </span>
            ))}
          </div>
        )}

        {/* Live replies carry the retrieved chunks; replayed history carries page numbers
            only, so this appears on the turn you just asked for. */}
        {turn.contexts?.length > 0 && (
          <details className="text-[11.5px] text-muted mt-2.5">
            <summary className="cursor-pointer font-medium hover:text-primary">
              Show the text it used
            </summary>
            <div className="mt-2 space-y-2">
              {turn.contexts.map((context, index) => (
                <div key={index} className="bg-surface-alt border border-border-light rounded-lg p-2.5">
                  <p className="text-subtle mb-1 font-medium">
                    Page {context.page_number} · match {Number(context.score ?? 0).toFixed(2)}
                  </p>
                  <p className="text-body leading-relaxed">{context.text}</p>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

export default ChatMessage;
