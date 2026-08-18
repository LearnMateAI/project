/**
 * One turn in a conversation.
 */

import ModeBadge from "./ModeBadge.jsx";

function ChatMessage({ turn }) {
  const isUser = turn.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="bg-ink text-white rounded-2xl rounded-br-md px-4 py-2 max-w-[80%] whitespace-pre-wrap">
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
      <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-md px-4 py-3 max-w-[85%]">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <ModeBadge mode={turn.mode} topScore={turn.top_score} />
          {turn.score !== null && turn.score !== undefined && (
            <span className="text-xs text-muted">Reviewed {turn.score}/100</span>
          )}
          {turn.attempts > 1 && (
            <span className="text-xs text-muted">{turn.attempts} attempts</span>
          )}
        </div>

        {turn.standalone_query && turn.standalone_query !== turn.query && (
          <p className="text-xs text-muted italic mb-2">
            Searched for: {turn.standalone_query}
          </p>
        )}

        <div className="whitespace-pre-wrap text-gray-800">{turn.content}</div>

        {flagged && (
          <p className="text-xs text-pending mt-2">
            This scored below the pass mark. Check it against the document.
          </p>
        )}

        {uniquePages.length > 0 && (
          <p className="text-xs text-muted mt-2">
            From page{uniquePages.length === 1 ? "" : "s"} {uniquePages.join(", ")}
          </p>
        )}

        {turn.contexts?.length > 0 && (
          <details className="text-xs text-muted mt-2">
            <summary className="cursor-pointer">Show the text it used</summary>
            <div className="mt-2 space-y-2">
              {turn.contexts.map((context, index) => (
                <div key={index} className="bg-paper rounded-lg p-2">
                  <p className="text-muted mb-1">
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
