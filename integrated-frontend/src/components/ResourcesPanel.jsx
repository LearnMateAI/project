/**
 * Generate study material from one document, and list what has already been generated.
 *
 * The form's job is to make `scope` understandable, because it is the field that decides
 * whether the result is any good and it is not a speed setting:
 *
 *   passage    one continuous extract -- optionally the pages that best match a topic.
 *              Seconds. "Five questions about directors' duties."
 *   document   the whole PDF, read in groups and pooled (folded, for a summary). Minutes.
 *              "Forty questions about this book."
 *
 * Asking for forty questions at passage scope does not fail. It quietly gives you forty
 * questions about the opening six thousand characters, which is why the choice is spelled
 * out here rather than left as a dropdown with two words in it.
 *
 * Two backend rules are enforced by the form rather than discovered as a 400: `count` and
 * `per_page` are mutually exclusive, and `per_page` does not apply to summaries.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RESOURCE_TYPES, generateResource, listResources, resourceLabel } from "../api/resources.js";
import { useJob } from "../hooks/useJob.js";
import JobProgress from "./JobProgress.jsx";

function ResourcesPanel({ documentId, documentStatus, pageCount }) {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);

  const [resourceType, setResourceType] = useState("keypoints");
  const [scope, setScope] = useState("passage");
  const [topic, setTopic] = useState("");
  const [amountMode, setAmountMode] = useState("total"); // "total" | "per_page"
  const [count, setCount] = useState(8);
  const [perPage, setPerPage] = useState(2);
  const [evaluate, setEvaluate] = useState(true);

  const job = useJob();

  const selectedType = RESOURCE_TYPES.find((entry) => entry.type === resourceType);
  const notReady = documentStatus !== "Ready";
  // A rate per page only makes sense for the pooled types, and only across the document.
  const canUsePerPage = scope === "document" && selectedType?.pooled;
  const usingPerPage = canUsePerPage && amountMode === "per_page";

  const fetchResources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listResources({ documentId });
      setResources(res.data);
    } catch {
      setResources([]);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    // Fetch-on-mount, and again whenever the selected document changes. The rule below
    // guards against cascading renders from derived state; this is a request to an
    // external system, which is what effects are for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchResources();
    job.reset();
    // job.reset is stable; re-running this on it would clear the panel on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchResources]);

  async function handleGenerate(e) {
    e.preventDefault();

    const result = await job.run(() =>
      generateResource({
        documentId,
        resourceType,
        scope,
        topic: scope === "passage" ? topic : null,
        // Exactly one of the two, never both -- the backend rejects both together.
        count: usingPerPage ? null : Number(count),
        perPage: usingPerPage ? Number(perPage) : null,
        evaluate,
      }),
    );

    if (result) await fetchResources();
  }

  const scopeChoices = [
    {
      value: "passage",
      title: "One passage",
      hint: "A single extract, or the pages that best match a topic. Takes seconds.",
    },
    {
      value: "document",
      title: "The whole document",
      hint: `Reads ${pageCount ? `all ${pageCount} pages` : "every page"} in groups and pools the results. Takes minutes, and is the only way to cover the whole PDF.`,
    },
  ];

  return (
    <section className="card">
      <div className="card-head">
        <h3>Generate study material</h3>
        <span className="icon-tile icon-tile-soft w-10 h-10">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
        </span>
      </div>

      <div className="card-body">
        {notReady && (
          <p className="notice notice-warn mb-4">
            {documentStatus === "Failed Processing"
              ? "This document could not be processed, so nothing can be generated from it."
              : "This document is still being processed — generation becomes available once it is Ready."}
          </p>
        )}

        <form onSubmit={handleGenerate} className="space-y-4">
          <div>
            <label className="field-label" htmlFor="resource-type">
              What to generate
            </label>
            <select
              id="resource-type"
              value={resourceType}
              onChange={(e) => setResourceType(e.target.value)}
              disabled={notReady || job.isRunning}
              className="select"
            >
              {RESOURCE_TYPES.map((entry) => (
                <option key={entry.type} value={entry.type}>
                  {entry.label}
                </option>
              ))}
            </select>
          </div>

          <fieldset disabled={notReady || job.isRunning} className="border-0 p-0 m-0">
            <legend className="field-label">How much to read</legend>
            {/* Cards rather than bare radios: scope is the field that decides whether the
                result is any good, and it deserves to be the biggest thing on the form. */}
            <div className="grid gap-2 sm:grid-cols-2">
              {scopeChoices.map((choice) => (
                <label
                  key={choice.value}
                  className={`rounded-xl border p-3 cursor-pointer transition-colors ${
                    scope === choice.value
                      ? "border-primary bg-primary-soft"
                      : "border-border hover:border-border-strong"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="scope"
                      value={choice.value}
                      checked={scope === choice.value}
                      onChange={() => setScope(choice.value)}
                    />
                    <span className="text-[13px] font-semibold text-heading">{choice.title}</span>
                  </span>
                  <span className="block text-[11.5px] text-muted mt-1 leading-relaxed">
                    {choice.hint}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          {scope === "passage" && (
            <div>
              <label className="field-label" htmlFor="topic">
                Topic <span className="font-normal text-muted">(optional)</span>
              </label>
              <input
                id="topic"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. directors' duties"
                disabled={notReady || job.isRunning}
                className="input"
              />
              <p className="field-hint">
                Picks the pages that best match. Left empty, the opening of the document is used.
              </p>
            </div>
          )}

          <div className="flex gap-3 items-end">
            {canUsePerPage && (
              <div className="w-36">
                <label className="field-label" htmlFor="amount-mode">
                  Amount
                </label>
                <select
                  id="amount-mode"
                  value={amountMode}
                  onChange={(e) => setAmountMode(e.target.value)}
                  disabled={job.isRunning}
                  className="select"
                >
                  <option value="total">In total</option>
                  <option value="per_page">Per page</option>
                </select>
              </div>
            )}

            <div className="flex-1">
              <label className="field-label" htmlFor="amount">
                {usingPerPage ? `${selectedType.countLabel} per page` : `How many ${selectedType.countLabel}`}
              </label>
              <input
                id="amount"
                type="number"
                min={1}
                max={usingPerPage ? 10 : 200}
                value={usingPerPage ? perPage : count}
                onChange={(e) => (usingPerPage ? setPerPage(e.target.value) : setCount(e.target.value))}
                disabled={notReady || job.isRunning}
                className="input"
              />
            </div>
          </div>

          <label className="flex items-start gap-2.5 rounded-xl border border-border p-3 cursor-pointer hover:border-border-strong">
            <input
              type="checkbox"
              checked={evaluate}
              onChange={(e) => setEvaluate(e.target.checked)}
              disabled={notReady || job.isRunning}
              className="mt-0.5"
            />
            <span>
              <span className="block text-[13px] font-semibold text-heading">Review before showing</span>
              <span className="block text-[11.5px] text-muted mt-0.5 leading-relaxed">
                A second model grades the result and one retry is allowed. Turning this off is
                about twice as fast, and nothing checks what comes back.
              </span>
            </span>
          </label>

          <button type="submit" disabled={notReady || job.isRunning} className="btn-primary w-full py-2.5">
            {job.isRunning ? (
              <>
                <span className="spinner spinner-light" />
                Generating...
              </>
            ) : (
              `Generate ${selectedType.label}`
            )}
          </button>
        </form>

        <JobProgress job={job} className="mt-3" />

        {job.isDone && job.result && (
          <div className="notice notice-success mt-3 flex-col items-start">
            <Link to={`/resources/${job.result.id}`} className="font-semibold no-underline hover:underline">
              View the {resourceLabel(job.result.resource_type)} →
            </Link>
            {/* Whole-document runs report what was asked for against what came back. The
                backend never pads a short set, so an unexplained gap would look like a bug. */}
            {job.result.requested && job.result.generated < job.result.requested && (
              <p className="text-[11.5px] mt-1 opacity-80">
                {job.result.generated} of the {job.result.requested} asked for — the document did
                not support more, or the rest repeated what was already there.
              </p>
            )}
          </div>
        )}

        <h4 className="text-[13px] font-bold uppercase tracking-wider text-muted mt-6 mb-1">
          Already generated
        </h4>
        {loading ? (
          <p className="text-[13px] text-muted py-2">Loading...</p>
        ) : resources.length === 0 ? (
          <p className="text-[13px] text-muted py-2">Nothing yet for this document.</p>
        ) : (
          <ul className="m-0 p-0 list-none">
            {resources.map((resource) => (
              <li key={resource.id} className="flex justify-between items-center gap-3 py-2.5 border-b border-border-light last:border-0">
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium text-heading">
                    {resourceLabel(resource.resource_type)}
                    {resource.accepted === false && resource.score !== null && (
                      <span className="badge badge-amber ml-2">flagged</span>
                    )}
                  </span>
                  <span className="block text-[11.5px] text-subtle">
                    {new Date(resource.created_at).toLocaleString()}
                  </span>
                </span>
                <Link
                  to={`/resources/${resource.id}`}
                  className="text-[12.5px] font-semibold text-primary no-underline hover:underline shrink-0"
                >
                  View
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default ResourcesPanel;
