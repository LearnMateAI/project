/**
 * What this user has done, and how well it scored.
 *
 * The second half is the interesting one, and it exists because the backend grades its own
 * output: every generation is scored by a separate judge model and every verdict is
 * logged, passes included. So "how good is the material this produced" has a measured
 * answer rather than an impression.
 *
 * Two numbers repay reading properly:
 *
 *   distinct   how many different scores the judge has ever given. Clustered in a narrow
 *              band means it cannot separate good from bad at any threshold, however the
 *              threshold is set -- a broken gate that looks like a working one. The range
 *              plot below shows this at a glance: a short bar is a judge with one opinion.
 *   stages     which gate decided each attempt. `validator` dominating means the
 *              generation prompt needs work, not the threshold. That is invisible from a
 *              pass rate alone, which is why it is here.
 *
 * Every plot here is single-hue and labelled on its axis, so no colour is asked to carry
 * identity, and every table stays on the page underneath its chart.
 */

import { useEffect, useState } from "react";
import { getAnalytics } from "../api/analytics.js";
import { errorMessage } from "../api/client.js";
import { resourceLabel } from "../api/resources.js";
import { BarChart, MeterRow, ProgressRing } from "../components/charts.jsx";

const STAGE_NOTES = {
  judge: "the judge model scored it",
  validator: "structural checks rejected it before the judge ran",
  parse: "the generator's output could not be read as JSON",
  skipped: "evaluation was switched off for that run",
};

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

/**
 * One type's score range: lowest to highest as a bar, the median as a dot, the pass mark as
 * a rule across it. Read sideways, a bar that barely spans anything is the "distinct"
 * problem made visible -- a judge giving everything the same mark.
 */
function ScoreRange({ label, row, threshold }) {
  return (
    <div className="py-3 border-b border-border-light last:border-0">
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <span className="text-[13px] font-semibold text-heading">{label}</span>
        <span className="text-[11.5px] text-muted tabular-nums">
          median <span className="font-semibold text-heading">{row.median}</span> · {row.n} judged ·{" "}
          {row.distinct} distinct
        </span>
      </div>

      <div className="relative h-6">
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-2 rounded-full bg-border-light" />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-2 rounded-full bg-primary-light"
          style={{ left: `${row.min}%`, width: `${Math.max(1, row.max - row.min)}%` }}
        />
        <span
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-primary ring-2 ring-white"
          style={{ left: `${row.median}%` }}
          title={`Median ${row.median}`}
        />
        {/* The pass mark, as a rule rather than a colour change: the threshold is a fact
            about the gate, not about this type's scores. */}
        <span
          className="absolute inset-y-0 border-l border-dashed border-subtle"
          style={{ left: `${threshold}%` }}
          title={`Pass mark ${threshold}`}
        />
      </div>

      <div className="flex justify-between text-[11px] text-subtle mt-1 tabular-nums">
        <span>{row.min}</span>
        <span>{row.max}</span>
      </div>
    </div>
  );
}

function Analytics() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getAnalytics()
      .then((res) => setStats(res.data))
      .catch((err) => setError(errorMessage(err, "Could not load your analytics.")))
      .finally(() => setLoading(false));
  }, []);

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

  const resources = stats.resources || {};
  const byType = resources.by_type || {};
  const evaluation = stats.evaluation || {};
  const scores = evaluation.scores || {};
  const stages = evaluation.stages || {};
  const threshold = evaluation.threshold ?? 70;

  const hasScores = Object.keys(scores).length > 0;
  const totalStages = Object.values(stages).reduce((sum, n) => sum + n, 0);
  const acceptance =
    resources.acceptance_rate === null || resources.acceptance_rate === undefined
      ? null
      : resources.acceptance_rate * 100;

  const typeBars = Object.entries(byType).map(([task, entry]) => ({
    label: resourceLabel(task).replace("Practice Questions", "Practice"),
    value: entry.total,
  }));

  return (
    <div>
      <div className="page-header">
        <h1>Your Analytics</h1>
        <p>What you have generated, and what the reviewer made of it</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-5">
        <Kpi label="Documents" value={stats.documents ?? 0} icon={KPI_ICONS.documents} />
        <Kpi label="Resources generated" value={resources.total ?? 0} icon={KPI_ICONS.resources} />
        <Kpi label="Conversations" value={stats.sessions ?? 0} icon={KPI_ICONS.sessions} />
        <Kpi label="Questions asked" value={stats.questions_asked ?? 0} icon={KPI_ICONS.questions} />
      </div>

      <div className="grid gap-5 xl:grid-cols-3 items-start mb-5">
        <section className="card">
          <div className="card-head">
            <h2>Review outcomes</h2>
          </div>
          <div className="card-body flex flex-col items-center text-center">
            {acceptance === null ? (
              <p className="text-[13px] text-muted py-6 m-0">Nothing generated yet.</p>
            ) : (
              <>
                <ProgressRing value={acceptance} size={132} stroke={11} label="passed" />
                <p className="text-[13px] text-muted mt-4 m-0">
                  <span className="font-semibold text-heading">{resources.accepted}</span> of{" "}
                  <span className="font-semibold text-heading">{resources.total}</span> generations
                  cleared the pass mark of {threshold}.
                </p>
              </>
            )}
          </div>
        </section>

        <section className="card xl:col-span-2">
          <div className="card-head">
            <div>
              <h2>Resources by type</h2>
              <p className="text-[12px] text-muted mt-0.5">How many of each you have generated</p>
            </div>
          </div>
          <div className="px-2 pt-4">
            <BarChart
              data={typeBars}
              height={196}
              formatValue={(n) => `${n} generated`}
              emptyMessage="Nothing generated yet."
            />
          </div>

          {Object.keys(byType).length > 0 && (
            <div className="card-body pt-1 space-y-3.5">
              {Object.entries(byType).map(([task, entry]) => (
                <MeterRow
                  key={task}
                  label={`${resourceLabel(task)} passed review`}
                  value={entry.accepted}
                  total={entry.total}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-2 items-start">
        <section className="card">
          <div className="card-head">
            <div>
              <h2>How the evaluator decided</h2>
              <p className="text-[12px] text-muted mt-0.5">
                Cheap structural checks first, then the judge model
              </p>
            </div>
          </div>

          <div className="card-body">
            {totalStages === 0 ? (
              <p className="text-[13px] text-muted m-0">No evaluations recorded yet.</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(stages).map(([stage, n]) => (
                  <MeterRow
                    key={stage}
                    label={stage}
                    value={n}
                    total={totalStages}
                    hint={STAGE_NOTES[stage] || ""}
                  />
                ))}
              </div>
            )}

            {stages.validator > (stages.judge || 0) && (
              <p className="notice notice-warn mt-4">
                More attempts are being rejected by the structural checks than reach the judge.
                That points at the generation prompt, not at the pass mark.
              </p>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <div>
              <h2>Score distribution</h2>
              <p className="text-[12px] text-muted mt-0.5">
                Lowest to highest, out of 100. The dashed rule is the pass mark of {threshold}.
              </p>
            </div>
          </div>

          <div className="card-body">
            {!hasScores ? (
              <p className="text-[13px] text-muted m-0">
                Nothing has been judged yet — generate something with review switched on.
              </p>
            ) : (
              <>
                {Object.entries(scores).map(([task, row]) => (
                  <ScoreRange key={task} label={resourceLabel(task)} row={row} threshold={threshold} />
                ))}
                <p className="text-[11.5px] text-muted mt-3 leading-relaxed">
                  <span className="font-semibold text-heading">Distinct</span> is how many different
                  scores the judge has given. A low number next to a large sample means it is not
                  separating good work from bad, and no pass mark would fix that.
                </p>
              </>
            )}
          </div>
        </section>
      </div>

      {/* The same numbers as a table -- every figure above is readable here without a
          chart, which is the point. */}
      {hasScores && (
        <section className="card mt-5 overflow-hidden">
          <div className="card-head">
            <h2>All judged scores</h2>
          </div>
          <div className="overflow-x-auto p-4">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th className="num">Judged</th>
                  <th className="num">Lowest</th>
                  <th className="num">Median</th>
                  <th className="num">Highest</th>
                  <th className="num">Mean</th>
                  <th className="num">Distinct</th>
                  <th className="num">Pass rate</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(scores).map(([task, row]) => (
                  <tr key={task}>
                    <td className="font-medium text-heading">{resourceLabel(task)}</td>
                    <td className="num">{row.n}</td>
                    <td className="num">{row.min}</td>
                    <td className="num">{row.median}</td>
                    <td className="num">{row.max}</td>
                    <td className="num">{row.mean}</td>
                    <td className="num">{row.distinct}</td>
                    <td className="num font-semibold text-heading">
                      {Math.round(row.pass_rate * 100)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

export default Analytics;
