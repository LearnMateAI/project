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
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-lg px-4 py-2 max-w-[80%] whitespace-pre-wrap">
          {turn.content}
        </div>
      </div>
    );
  }

  const pages = (turn.pages || []).filter((page) => page !== null && page !== undefined);
  const uniquePages = [...new Set(pages)].sort((a, b) => a - b);
  const flagged = turn.accepted === false && turn.score !== null && turn.score !== undefined;

  return (
    <div className="flex justify-start">
      <div className="bg-white border rounded-lg px-4 py-3 max-w-[85%] shadow-sm">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <ModeBadge mode={turn.mode} topScore={turn.top_score} />
          {turn.score !== null && turn.score !== undefined && (
            <span className="text-xs text-gray-500">Reviewed {turn.score}/100</span>
          )}
          {turn.attempts > 1 && (
            <span className="text-xs text-gray-400">{turn.attempts} attempts</span>
          )}
        </div>

        {/* Shown only when the rewrite actually changed the question. On a follow-up like
            "what about his powers?" the retrieval is only as good as this line, so a bad
            answer is usually a bad rewrite -- and invisible without it. */}
        {turn.standalone_query && turn.standalone_query !== turn.query && (
          <p className="text-xs text-gray-500 italic mb-2">
            Searched for: {turn.standalone_query}
          </p>
        )}

        <div className="whitespace-pre-wrap text-gray-800">{turn.content}</div>

        {flagged && (
          <p className="text-xs text-amber-700 mt-2">
            This scored below the pass mark. Check it against the document.
          </p>
        )}

        {uniquePages.length > 0 && (
          <p className="text-xs text-gray-500 mt-2">
            From page{uniquePages.length === 1 ? "" : "s"} {uniquePages.join(", ")}
          </p>
        )}

        {/* Live replies carry the retrieved chunks; replayed history carries page numbers
            only, so this appears on the turn you just asked for. */}
        {turn.contexts?.length > 0 && (
          <details className="text-xs text-gray-500 mt-2">
            <summary className="cursor-pointer">Show the text it used</summary>
            <div className="mt-2 space-y-2">
              {turn.contexts.map((context, index) => (
                <div key={index} className="bg-gray-50 border rounded p-2">
                  <p className="text-gray-400 mb-1">
                    Page {context.page_number} · match {Number(context.score ?? 0).toFixed(2)}
                  </p>
                  <p className="text-gray-700">{context.text}</p>
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
