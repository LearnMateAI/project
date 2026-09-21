/**
 * Where the class gets stuck in one document.
 *
 * Every student who uploads the same notes shares one document, so every question any of
 * them asks is evidence about the notes themselves. The backend clusters those questions
 * into topics and maps them onto pages (GET /api/analytics/documents/:id/heatmap); this
 * draws the result:
 *
 *   the strip   one cell per page, darker where more students asked and the answers
 *               landed worse (not in the document, low-scored, asked again). Hatched
 *               cells had too few students to show without identifying them.
 *   the topics  what the questions were about, as keywords -- never the questions.
 *
 * Clicking a page hands it to `onSelectPage`, which the workspace uses to open that page
 * in the reader beside it.
 */

import { useCallback, useEffect, useState } from "react";
import { getDocumentHeatmap } from "../api/analytics.js";
import { errorMessage } from "../api/client.js";

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function cellTitle(page, unit) {
  const label = `${unit} ${page.page}`;
  if (page.suppressed) return `${label} · fewer students than the privacy threshold`;
  if (!page.questions) return `${label} · no questions yet`;
  const s = page.signals || {};
  return [
    `${label} · ${page.questions} question${page.questions === 1 ? "" : "s"} from ${page.distinct_users} students`,
    `${pct(s.general)} not answerable from the document`,
    `${pct(s.low_score)} low-scored answers`,
    `${pct(s.repeat)} asked again`,
  ].join("\n");
}

function ConfusionHeatmap({ documentId, onSelectPage, selectedPage, unit = "Page" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(
    (refresh = false) => {
      if (!documentId) return;
      setLoading(true);
      setError("");
      getDocumentHeatmap(documentId, { refresh })
        .then((res) => setData(res.data))
        .catch((err) => setError(errorMessage(err, "Could not load class insights.")))
        .finally(() => setLoading(false));
    },
    [documentId],
  );

  useEffect(() => {
    // Fetch when the document changes: a request to an external system, which is what an
    // effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  if (loading && !data) {
    return (
      <p className="flex items-center gap-2.5 text-[13px] text-muted m-0">
        <span className="spinner" />
        Mining the class&rsquo;s questions...
      </p>
    );
  }
  if (error) return <p className="notice notice-error m-0">{error}</p>;
  if (!data) return null;

  const pages = data.pages || [];
  const max = Math.max(0, ...pages.map((page) => page.confusion || 0));
  const topics = (data.topics || []).slice(0, 6);
  const cacheRate = data.answer_cache?.hit_rate;

  if (!data.n_questions) {
    return (
      <p className="notice notice-info m-0">
        No questions about this document yet. Once students ask, this shows which pages they
        struggle with.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12.5px] text-muted m-0">
          {data.n_questions} question{data.n_questions === 1 ? "" : "s"}
          {data.n_users != null && ` from ${data.n_users} student${data.n_users === 1 ? "" : "s"}`}
          {cacheRate != null && ` · ${pct(cacheRate)} answered by reusing a verified answer`}
        </p>
        <button type="button" className="btn-ghost text-[12px]" onClick={() => load(true)} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="heat-strip" role="list" aria-label={`Confusion by ${unit.toLowerCase()}`}>
        {pages.map((page) => {
          const heat = page.suppressed || !max ? 0 : (page.confusion || 0) / max;
          return (
            <button
              key={page.page}
              type="button"
              role="listitem"
              className={[
                "heat-cell",
                page.suppressed ? "is-suppressed" : "",
                heat > 0.55 ? "is-hot" : "",
                selectedPage === page.page ? "is-selected" : "",
              ].join(" ")}
              style={{ "--heat": heat.toFixed(3) }}
              title={cellTitle(page, unit)}
              disabled={page.suppressed}
              onClick={() => onSelectPage?.(page.page)}
            >
              {page.page}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <span className="heat-legend">
          Fewer questions <span className="heat-legend-ramp" /> More confusion
        </span>
        <span className="heat-legend">
          <span className="heat-cell is-suppressed w-3.5 h-3.5" aria-hidden="true" />
          Fewer than {data.k} students (hidden)
        </span>
      </div>

      {topics.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle m-0 mb-2">
            What the class asks about
          </p>
          <ul className="space-y-2 m-0 p-0 list-none">
            {topics.map((topic) => (
              <li key={topic.id} className="bg-surface-alt border border-border-light rounded-lg px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[13px] font-semibold text-heading">
                    {topic.terms.length ? topic.terms.join(" · ") : "Unlabelled topic"}
                  </span>
                  {topic.signals?.general >= 0.3 && (
                    <span className="badge badge-amber" title="Share of these questions the document could not answer">
                      <span className="badge-dot" />
                      {pct(topic.signals.general)} not in the notes
                    </span>
                  )}
                  {topic.signals?.low_score >= 0.3 && (
                    <span className="badge badge-red" title="Share of judged answers below the pass mark">
                      <span className="badge-dot" />
                      {pct(topic.signals.low_score)} low-scored
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                  <span className="text-[11.5px] text-muted">
                    {topic.size} questions · {topic.distinct_users} students
                  </span>
                  {topic.pages.map((entry) => (
                    <button
                      key={entry.page}
                      type="button"
                      className="cite cursor-pointer"
                      onClick={() => onSelectPage?.(entry.page)}
                      title={`${pct(entry.share)} of this topic's questions landed here`}
                    >
                      <span className="cite-page">
                        {unit === "Page" ? "p." : unit} {entry.page}
                      </span>
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
          {data.suppressed_topics > 0 && (
            <p className="text-[11.5px] text-subtle mt-2 mb-0">
              {data.suppressed_topics} smaller topic{data.suppressed_topics === 1 ? "" : "s"} hidden
              for privacy.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default ConfusionHeatmap;
