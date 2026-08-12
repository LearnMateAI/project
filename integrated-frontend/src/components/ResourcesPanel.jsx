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

  return (
    <div className="bg-white rounded-lg shadow-sm p-4 mt-4">
      <h3 className="font-medium mb-3">Generate study material</h3>

      {notReady && (
        <p className="text-sm text-amber-600 mb-3">
          {documentStatus === "Failed Processing"
            ? "This document could not be processed, so nothing can be generated from it."
            : "This document is still being processed — generation becomes available once it is Ready."}
        </p>
      )}

      <form onSubmit={handleGenerate} className="space-y-3">
        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="resource-type">
            What to generate
          </label>
          <select
            id="resource-type"
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            disabled={notReady || job.isRunning}
            className="w-full border rounded px-2 py-1.5 text-sm"
          >
            {RESOURCE_TYPES.map((entry) => (
              <option key={entry.type} value={entry.type}>
                {entry.label}
              </option>
            ))}
          </select>
        </div>

        <fieldset disabled={notReady || job.isRunning}>
          <legend className="block text-sm font-medium mb-1">How much to read</legend>
          <div className="space-y-1">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="scope"
                value="passage"
                checked={scope === "passage"}
                onChange={() => setScope("passage")}
                className="mt-1"
              />
              <span>
                <span className="font-medium">One passage</span>
                <span className="block text-xs text-gray-500">
                  A single extract, or the pages that best match a topic. Takes seconds.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="scope"
                value="document"
                checked={scope === "document"}
                onChange={() => setScope("document")}
                className="mt-1"
              />
              <span>
                <span className="font-medium">The whole document</span>
                <span className="block text-xs text-gray-500">
                  Reads {pageCount ? `all ${pageCount} pages` : "every page"} in groups and pools
                  the results. Takes minutes, and is the only way to cover the whole PDF.
                </span>
              </span>
            </label>
          </div>
        </fieldset>

        {scope === "passage" && (
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="topic">
              Topic <span className="font-normal text-gray-500">(optional)</span>
            </label>
            <input
              id="topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. directors' duties"
              disabled={notReady || job.isRunning}
              className="w-full border rounded px-2 py-1.5 text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">
              Picks the pages that best match. Left empty, the opening of the document is used.
            </p>
          </div>
        )}

        <div className="flex gap-3 items-end">
          {canUsePerPage && (
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="amount-mode">
                Amount
              </label>
              <select
                id="amount-mode"
                value={amountMode}
                onChange={(e) => setAmountMode(e.target.value)}
                disabled={job.isRunning}
                className="border rounded px-2 py-1.5 text-sm"
              >
                <option value="total">In total</option>
                <option value="per_page">Per page</option>
              </select>
            </div>
          )}

          <div className="flex-1">
            <label className="block text-sm font-medium mb-1" htmlFor="amount">
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
              className="w-full border rounded px-2 py-1.5 text-sm"
            />
          </div>
        </div>

        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={evaluate}
            onChange={(e) => setEvaluate(e.target.checked)}
            disabled={notReady || job.isRunning}
            className="mt-1"
          />
          <span>
            Review before showing
            <span className="block text-xs text-gray-500">
              A second model grades the result and one retry is allowed. Turning this off is
              about twice as fast, and nothing checks what comes back.
            </span>
          </span>
        </label>

        <button
          type="submit"
          disabled={notReady || job.isRunning}
          className="w-full bg-blue-600 text-white rounded py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {job.isRunning ? "Generating..." : `Generate ${selectedType.label}`}
        </button>
      </form>

      <JobProgress job={job} className="mt-3" />

      {job.isDone && job.result && (
        <div className="mt-3 text-sm bg-green-50 border border-green-200 rounded p-2">
          <Link to={`/resources/${job.result.id}`} className="text-blue-700 hover:underline font-medium">
            View the {resourceLabel(job.result.resource_type)} →
          </Link>
          {/* Whole-document runs report what was asked for against what came back. The
              backend never pads a short set, so an unexplained gap would look like a bug. */}
          {job.result.requested && job.result.generated < job.result.requested && (
            <p className="text-xs text-gray-600 mt-1">
              {job.result.generated} of the {job.result.requested} asked for — the document did
              not support more, or the rest repeated what was already there.
            </p>
          )}
        </div>
      )}

      <h4 className="font-medium text-sm mt-5 mb-2">Already generated</h4>
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : resources.length === 0 ? (
        <p className="text-sm text-gray-500">Nothing yet for this document.</p>
      ) : (
        <ul className="divide-y">
          {resources.map((resource) => (
            <li key={resource.id} className="py-2 flex justify-between items-center gap-2">
              <span className="text-sm min-w-0">
                {resourceLabel(resource.resource_type)}
                <span className="text-gray-400 text-xs ml-2">
                  {new Date(resource.created_at).toLocaleString()}
                </span>
                {resource.accepted === false && resource.score !== null && (
                  <span className="text-xs text-amber-700 ml-2">flagged</span>
                )}
              </span>
              <Link
                to={`/resources/${resource.id}`}
                className="text-sm text-blue-600 hover:underline shrink-0"
              >
                View
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default ResourcesPanel;
