/**
 * Page and paragraph citations on an assistant reply.
 *
 * Legal study needs the pin-cite, not a vague "from your document". A chip is p.12 ¶2
 * when the retrieved chunk carries a per-page index; otherwise it is just the page,
 * which is what stored history had before citations were persisted.
 */

function fromTurn(turn) {
  if (Array.isArray(turn.citations) && turn.citations.length) {
    return turn.citations
      .filter((cite) => cite && cite.page != null)
      .map((cite) => ({
        page: cite.page,
        paragraph: cite.paragraph ?? null,
      }));
  }
  if (Array.isArray(turn.contexts) && turn.contexts.length) {
    return turn.contexts
      .filter((context) => context?.page_number != null)
      .map((context) => ({
        page: context.page_number,
        paragraph: context.paragraph ?? (context.chunk_index != null ? context.chunk_index + 1 : null),
      }));
  }
  return [...new Set((turn.pages || []).filter((page) => page != null))].map((page) => ({
    page,
    paragraph: null,
  }));
}

function label(cite) {
  const page = `p. ${cite.page}`;
  return cite.paragraph != null ? `${page} ¶${cite.paragraph}` : page;
}

function CitationChips({ turn }) {
  const cites = fromTurn(turn);
  if (!cites.length) return null;

  const unique = [];
  const seen = new Set();
  for (const cite of cites) {
    const key = `${cite.page}:${cite.paragraph ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(cite);
  }
  unique.sort((a, b) => a.page - b.page || (a.paragraph || 0) - (b.paragraph || 0));

  return (
    <div className="mt-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle m-0 mb-1.5">
        Cited
      </p>
      <div className="chip-row">
        {unique.map((cite) => (
          <span key={`${cite.page}-${cite.paragraph ?? "p"}`} className="cite" title="Retrieved passage">
            <span className="cite-page">{label(cite)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default CitationChips;
