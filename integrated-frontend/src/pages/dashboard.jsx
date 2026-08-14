/**
 * The workspace overview.
 *
 * Laid out the way a dashboard is read rather than the way the API is shaped: the three
 * things you might have come here to *do* sit at the top, the wide left column carries the
 * measurements, and the right column is the working column -- upload, and what you last
 * made.
 *
 * The activity chart is built from the resources' own `created_at`, not from a stats
 * endpoint: the backend has no time series, and seven days of counts derived on the client
 * is honest about what it is.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalytics } from "../api/analytics.js";
import { listResources, resourceLabel } from "../api/resources.js";
import DocumentsCard from "../components/DocumentsCard.jsx";
import { BarChart, LineChart } from "../components/charts.jsx";

const DAY_MS = 86400000;

const quickStart = [
  {
    to: "/documents",
    title: "Upload a document",
    caption: "PDF · up to 10 MB",
    icon: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5",
  },
  {
    to: "/chat",
    title: "Ask your documents",
    caption: "Answers cite their pages",
    icon: "M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155",
  },
  {
    to: "/resources",
    title: "Generate study material",
    caption: "Summaries, key points, MCQs",
    icon: "M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z",
  },
];

const figures = [
  {
    key: "documents",
    label: "Documents",
    to: "/documents",
    icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z",
  },
  {
    key: "resources",
    label: "Resources generated",
    to: "/resources",
    icon: "M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.331 0 4.472.89 6.042 2.346M12 6.042a8.967 8.967 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.346",
  },
  {
    key: "questions",
    label: "Questions asked",
    to: "/chat",
    icon: "M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z",
  },
];

function Dashboard() {
  const [resources, setResources] = useState([]);
  const [stats, setStats] = useState(null);

  const refresh = useCallback(async () => {
    // Neither call is worth failing the page over: a dashboard that renders the upload card
    // and two empty panels is far more useful than an error screen.
    try {
      const res = await listResources();
      setResources(res.data);
    } catch {
      setResources([]);
    }
    try {
      const res = await getAnalytics();
      setStats(res.data);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  // Seven days ending today, so the rightmost point is always "now" and an empty day is a
  // zero rather than a gap.
  const daily = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const buckets = Array.from({ length: 7 }, (_, index) => {
      const day = new Date(today.getTime() - (6 - index) * DAY_MS);
      return {
        label: day.toLocaleDateString(undefined, { weekday: "short" }),
        start: day.getTime(),
        value: 0,
      };
    });

    for (const resource of resources) {
      const created = new Date(resource.created_at).getTime();
      const bucket = buckets.find((entry) => created >= entry.start && created < entry.start + DAY_MS);
      if (bucket) bucket.value += 1;
    }
    return buckets;
  }, [resources]);

  const byType = useMemo(() => {
    const source = stats?.resources?.by_type || {};
    return Object.entries(source).map(([type, entry]) => ({
      label: resourceLabel(type).replace("Practice Questions", "Practice"),
      value: entry.total,
    }));
  }, [stats]);

  const recent = resources.slice(0, 5);
  const weekTotal = daily.reduce((sum, day) => sum + day.value, 0);

  const values = {
    documents: stats?.documents ?? 0,
    resources: stats?.resources?.total ?? 0,
    questions: stats?.questions_asked ?? 0,
  };

  return (
    <div>
      {/* Quick start ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 mb-3">
        <h2 className="section-title mb-0">Quick start</h2>
        <Link to="/tour" className="text-[12.5px] font-semibold text-primary no-underline hover:underline">
          Take a tour →
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 mb-6">
        {quickStart.map((action) => (
          <Link key={action.to} to={action.to} className="card card-hover p-4 flex items-center gap-4 no-underline">
            <span className="icon-tile">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
                <path strokeLinecap="round" strokeLinejoin="round" d={action.icon} />
              </svg>
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-semibold text-heading truncate">{action.title}</span>
              <span className="block text-[12px] text-muted truncate">{action.caption}</span>
            </span>
            <svg className="w-5 h-5 text-subtle shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </Link>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-3 items-start">
        {/* Measurements ──────────────────────────────────────────── */}
        <div className="xl:col-span-2 space-y-5">
          <section className="card">
            <div className="card-head">
              <div>
                <h2>Study activity</h2>
                <p className="text-[12px] text-muted mt-0.5">Resources you generated, last 7 days</p>
              </div>
              <span className="badge badge-blue">
                <span className="badge-dot" />
                {weekTotal} this week
              </span>
            </div>
            <div className="px-3 pb-3 pt-4">
              <LineChart
                data={daily}
                height={244}
                formatValue={(n) => `${n} resource${n === 1 ? "" : "s"}`}
                emptyMessage="Nothing generated in the last 7 days."
              />
            </div>
          </section>

          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-4">
              {figures.map((figure) => (
                <Link key={figure.key} to={figure.to} className="stat-row no-underline hover:border-border-strong transition-colors">
                  <span className="icon-circle">
                    <svg className="w-[19px] h-[19px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={figure.icon} />
                    </svg>
                  </span>
                  <span>
                    <span className="stat-label block">{figure.label}</span>
                    <span className="stat-value block">{values[figure.key]}</span>
                  </span>
                </Link>
              ))}
            </div>

            <section className="card">
              <div className="card-head">
                <h2>By type</h2>
              </div>
              <div className="px-2 pb-2 pt-3">
                <BarChart
                  data={byType}
                  height={216}
                  formatValue={(n) => `${n} generated`}
                  emptyMessage="Generate something to see the mix."
                />
              </div>
            </section>
          </div>
        </div>

        {/* Working column ────────────────────────────────────────── */}
        <div className="space-y-5">
          <DocumentsCard onUploaded={refresh} />

          <section className="card">
            <div className="card-head">
              <h2>Recent resources</h2>
              <Link to="/resources" className="text-[12.5px] font-semibold text-primary no-underline hover:underline">
                View all →
              </Link>
            </div>

            {recent.length === 0 ? (
              <p className="px-5 py-6 text-[13px] text-muted leading-relaxed">
                Once a document is ready, open it from Documents and generate summaries, key
                points, MCQs or practice questions.
              </p>
            ) : (
              <div>
                {recent.map((resource) => (
                  <Link key={resource.id} to={`/resources/${resource.id}`} className="list-row">
                    <span className="min-w-0">
                      <span className="block text-[13.5px] font-semibold text-heading truncate">
                        {resourceLabel(resource.resource_type)}
                      </span>
                      <span className="block text-[11.5px] text-subtle">
                        {new Date(resource.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </span>
                    </span>
                    <span
                      className={`badge shrink-0 ${
                        resource.score === null || resource.score === undefined
                          ? "badge-gray"
                          : resource.accepted
                            ? "badge-green"
                            : "badge-amber"
                      }`}
                    >
                      {resource.score === null || resource.score === undefined
                        ? "Not reviewed"
                        : `${resource.score}/100`}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
