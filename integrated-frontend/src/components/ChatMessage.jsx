/**
 * One turn in a conversation.
 *
 * A user turn is just text. An assistant turn carries an audit trail, and showing it is
 * the point of this component rather than an extra:
 *
 *   mode      whether the answer came from the document or from the model's own knowledge.
 *             The prose reads identically either way, so the badge is the only thing that
 *             can tell them apart -- see ModeBadge.
 *   pages     which pages it drew on, with the retrieved text behind a disclosure, so the
 *             answer can be checked against the source rather than trusted.
 *   score     what the judge gave it, and a warning when it did not clear the threshold.
 *
 * The same fields arrive on a live reply and on a turn replayed from history, so a resumed
 * conversation looks identical to one still in progress.
 */

import ModeBadge from "./ModeBadge.jsx";

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
        <div className="flex flex-wrap items-center gap-2 mb-2.5">
          <ModeBadge mode={turn.mode} topScore={turn.top_score} />
          {turn.score !== null && turn.score !== undefined && (
            <span className="text-[11.5px] text-muted">Reviewed {turn.score}/100</span>
          )}
          {turn.attempts > 1 && (
            <span className="text-[11.5px] text-subtle">{turn.attempts} attempts</span>
          )}
        </div>

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

        {uniquePages.length > 0 && (
          <p className="text-[11.5px] text-muted mt-2.5 flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            From page{uniquePages.length === 1 ? "" : "s"} {uniquePages.join(", ")}
          </p>
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
