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
 */

function ModeBadge({ mode, topScore, className = "" }) {
  const grounded = mode === "pdf";

  return (
    <span
      className={`inline-block text-xs rounded-full px-2.5 py-1 font-medium ${
        grounded ? "bg-ink-light text-ink" : "bg-gray-100 text-muted"
      } ${className}`}
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
