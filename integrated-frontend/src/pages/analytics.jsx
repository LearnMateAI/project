/**
 * What this user has done, and how well it scored.
 */

import { useEffect, useState } from "react";
import { getAnalytics } from "../api/analytics.js";
import { errorMessage } from "../api/client.js";
import { resourceLabel } from "../api/resources.js";

const STAGE_NOTES = {
  judge: "the judge model scored it",
  validator: "structural checks rejected it before the judge ran",
  parse: "the generator's output could not be read as JSON",
  skipped: "evaluation was switched off for that run",
};

function Stat({ label, value }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <p className="font-display text-2xl font-bold text-ink">{value}</p>
      <p className="text-sm text-muted">{label}</p>
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

  if (loading) return <p className="text-sm text-muted">Loading...</p>;
  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!stats) return null;

  const resources = stats.resources || {};
  const byType = resources.by_type || {};
  const evaluation = stats.evaluation || {};
  const scores = evaluation.scores || {};
  const stages = evaluation.stages || {};

  const hasScores = Object.keys(scores).length > 0;
  const totalStages = Object.values(stages).reduce((sum, n) => sum + n, 0);

  return (
    <div>
      <h1 className="font-display text-2xl font-bold mb-6 text-ink">Your Analytics</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <Stat label="Documents" value={stats.documents ?? 0} />
        <Stat label="Resources generated" value={resources.total ?? 0} />
        <Stat label="Conversations" value={stats.sessions ?? 0} />
        <Stat label="Questions asked" value={stats.questions_asked ?? 0} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-medium mb-1 text-ink">Resources by type</h2>
          <p className="text-sm text-muted mb-4">
            {resources.acceptance_rate === null || resources.acceptance_rate === undefined
              ? "Nothing generated yet."
              : `${resources.accepted} of ${resources.total} passed review (${Math.round(
                  resources.acceptance_rate * 100,
                )}%).`}
          </p>

          {Object.keys(byType).length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-gray-100">
                  <th className="pb-2">Type</th>
                  <th className="pb-2 text-right">Generated</th>
                  <th className="pb-2 text-right">Passed</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(byType).map(([task, entry]) => (
                  <tr key={task} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 text-gray-800">{resourceLabel(task)}</td>
                    <td className="py-2 text-right text-gray-800">{entry.total}</td>
                    <td className="py-2 text-right text-gray-800">{entry.accepted}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-medium mb-1 text-ink">How the evaluator decided</h2>
          <p className="text-sm text-muted mb-4">
            Every generation passes two gates: cheap structural checks first, then a judge
            model. This is which gate settled each attempt.
          </p>

          {totalStages === 0 ? (
            <p className="text-sm text-muted">No evaluations recorded yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {Object.entries(stages).map(([stage, n]) => (
                <li key={stage} className="flex justify-between gap-3">
                  <span>
                    <span className="font-medium text-ink">{stage}</span>
                    <span className="block text-xs text-muted">
                      {STAGE_NOTES[stage] || ""}
                    </span>
                  </span>
                  <span className="shrink-0 text-gray-800">
                    {n} <span className="text-muted">({Math.round((n / totalStages) * 100)}%)</span>
                  </span>
                </li>
              ))}
            </ul>
          )}

          {stages.validator > (stages.judge || 0) && (
            <p className="text-xs text-pending mt-3">
              More attempts are being rejected by the structural checks than reach the judge.
              That points at the generation prompt, not at the pass mark.
            </p>
          )}
        </section>
      </div>

      <section className="bg-white rounded-xl border border-gray-100 p-5 mt-6">
        <h2 className="font-medium mb-1 text-ink">Score distribution</h2>
        <p className="text-sm text-muted mb-4">
          Scores the judge gave, out of 100. The pass mark is {evaluation.threshold ?? 70}.
        </p>

        {!hasScores ? (
          <p className="text-sm text-muted">
            Nothing has been judged yet — generate something with review switched on.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-gray-100">
                  <th className="pb-2">Type</th>
                  <th className="pb-2 text-right">Judged</th>
                  <th className="pb-2 text-right">Lowest</th>
                  <th className="pb-2 text-right">Median</th>
                  <th className="pb-2 text-right">Highest</th>
                  <th className="pb-2 text-right">Mean</th>
                  <th className="pb-2 text-right">Distinct</th>
                  <th className="pb-2 text-right">Pass rate</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(scores).map(([task, row]) => (
                  <tr key={task} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 text-gray-800">{resourceLabel(task)}</td>
                    <td className="py-2 text-right text-gray-800">{row.n}</td>
                    <td className="py-2 text-right text-gray-800">{row.min}</td>
                    <td className="py-2 text-right text-gray-800">{row.median}</td>
                    <td className="py-2 text-right text-gray-800">{row.max}</td>
                    <td className="py-2 text-right text-gray-800">{row.mean}</td>
                    <td className="py-2 text-right text-gray-800">{row.distinct}</td>
                    <td className="py-2 text-right text-gray-800">{Math.round(row.pass_rate * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-muted mt-3">
              <span className="font-medium">Distinct</span> is how many different scores the
              judge has given. A low number next to a large sample means it is not separating
              good work from bad, and no pass mark would fix that.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

export default Analytics;
