/**
 * Where a chat answer came from.
 *
 * This is the most important thing on the chat screen. The agent runs in one of two modes,
 * decided by the retrieval score rather than by asking the model:
 *
 *   pdf      the top chunk cleared the relevance threshold, so the reply was written from
 *            those pages and judged strictly against them -- anything they do not support
 *            counts as a hallucination.
 *   general  nothing relevant came back, so the reply is the model's own knowledge about
 *            the subject. It may well be right. It is not from the student's document, and
 *            nothing checked it against one.
 *
 * The text of an answer looks the same either way, so the badge is the only thing that can
 * tell them apart, and reading a law summary that turned out to be general knowledge is
 * exactly the mistake this project exists to avoid.
 */

function ModeBadge({ mode, topScore, className = "" }) {
  const grounded = mode === "pdf";

  return (
    <span
      className={`inline-block text-xs border rounded px-2 py-0.5 ${
        grounded
          ? "bg-blue-50 text-blue-700 border-blue-200"
          : "bg-gray-100 text-gray-600 border-gray-200"
      } ${className}`}
      // A replayed turn carries the mode but not the retrieval score -- the stored meta
      // has no room for it -- so the number is omitted rather than shown as 0.00.
      title={
        grounded
          ? `Written from your document${
              topScore ? ` (best match ${Number(topScore).toFixed(2)})` : ""
            }.`
          : "Nothing relevant was found in your document, so this is the model's general knowledge."
      }
    >
      {grounded ? "From your document" : "General knowledge"}
    </span>
  );
}

export default ModeBadge;
