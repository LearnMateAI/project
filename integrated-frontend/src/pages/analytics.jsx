/**
 * What this user has done: four totals and seven days of activity.
 *
 * This page used to carry the evaluator's side of the story as well -- acceptance rate,
 * score ranges per type, which gate decided each attempt, and the whole judged-score table.
 * All of it is gone from the screen and none of it from the system: /api/analytics still
 * returns the evaluation block, and the backend still logs every verdict, so the display
 * can come back without anything being re-measured.
 *
 * The seven-day activity chart is the one figure not served by /api/analytics: the backend
 * keeps no time series, so it is bucketed on the client from the resources' own created_at.
 * That is honest about what it is, and it is why this page makes a second request.
 */

import { useEffect, useMemo, useState } from "react";
import { getAnalytics } from "../api/analytics.js";
import { errorMessage } from "../api/client.js";
import { listResources } from "../api/resources.js";
import { LineChart } from "../components/charts.jsx";

const DAY_MS = 86400000;

const KPI_ICONS = {
  documents: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z",
  resources: "M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.331 0 4.472.89 6.042 2.346M12 6.042a8.967 8.967 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.346",
  sessions: "M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155",
  questions: "M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z",
};

function Kpi({ label, value, icon }) {
  return (
    <div className="stat-card flex items-start justify-between gap-3">
      <div>
        <p className="stat-label">{label}</p>
        <p className="stat-value">{value}</p>
      </div>
      <span className="icon-circle w-10 h-10">
        <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
          <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
        </svg>
      </span>
    </div>
  );
}

function Analytics() {
  const [stats, setStats] = useState(null);
  // Named for what it is rather than `resources`, which further down is the *summary* block
  // out of /api/analytics. Two different shapes, and one of them is a list.
  const [generated, setGenerated] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getAnalytics()
      .then((res) => setStats(res.data))
      .catch((err) => setError(errorMessage(err, "Could not load your analytics.")))
      .finally(() => setLoading(false));
  }, []);

  // Separate from the stats call, and allowed to fail on its own: the activity chart is
  // derived from the resources' own timestamps because the backend keeps no time series,
  // so losing this costs one chart rather than the page.
  useEffect(() => {
    listResources()
      .then((res) => setGenerated(res.data))
      .catch(() => setGenerated([]));
  }, []);

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

    for (const resource of generated) {
      const created = new Date(resource.created_at).getTime();
      const bucket = buckets.find(
        (entry) => created >= entry.start && created < entry.start + DAY_MS,
      );
      if (bucket) bucket.value += 1;
    }
    return buckets;
  }, [generated]);

  const weekTotal = daily.reduce((sum, day) => sum + day.value, 0);

  if (loading) {
    return (
      <p className="flex items-center gap-2.5 text-[13px] text-muted">
        <span className="spinner" />
        Loading...
      </p>
    );
  }
  if (error) return <p className="notice notice-error">{error}</p>;
  if (!stats) return null;

  // Only the totals are read now. /api/analytics still returns the evaluation block --
  // score ranges, stage counts, acceptance rates -- and the backend still records all of
  // it; this page simply no longer puts it on screen.
  const resources = stats.resources || {};

  return (
    <div>
      <div className="page-header">
        <h1>Your Analytics</h1>
        
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-5">
        <Kpi label="Documents" value={stats.documents ?? 0} icon={KPI_ICONS.documents} />
        <Kpi label="Resources generated" value={resources.total ?? 0} icon={KPI_ICONS.resources} />
        <Kpi label="Conversations" value={stats.sessions ?? 0} icon={KPI_ICONS.sessions} />
        <Kpi label="Questions asked" value={stats.questions_asked ?? 0} icon={KPI_ICONS.questions} />
      </div>

      <section className="card mb-5">
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

    </div>
  );
}

export default Analytics;
