/**
 * Generate study material from one document, and list what has already been generated.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RESOURCE_TYPES, generateResource, listResources, resourceLabel } from "../api/resources.js";
import { qualityTone } from "./QualityBadge.jsx";
import { useJob } from "../hooks/useJob.js";
import JobProgress from "./JobProgress.jsx";

function ResourcesPanel({ documentId, documentStatus, pageCount }) {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);

  const [resourceType, setResourceType] = useState("keypoints");
  const [scope, setScope] = useState("passage");
  const [topic, setTopic] = useState("");
  const [amountMode, setAmountMode] = useState("total");
  const [count, setCount] = useState(8);
  const [perPage, setPerPage] = useState(2);
  const [evaluate, setEvaluate] = useState(true);

  const job = useJob();

  const selectedType = RESOURCE_TYPES.find((entry) => entry.type === resourceType);
  const notReady = documentStatus !== "Ready";
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
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchResources();
    job.reset();
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
        count: usingPerPage ? null : Number(count),
        perPage: usingPerPage ? Number(perPage) : null,
        evaluate,
      }),
    );

    if (result) await fetchResources();
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4 mt-4">
      <h3 className="font-medium mb-3 text-ink">Generate study material</h3>

      {notReady && (
        <p className="text-sm text-pending mb-3">
          {documentStatus === "Failed Processing"
            ? "This document could not be processed, so nothing can be generated from it."
            : "This document is still being processed — generation becomes available once it is Ready."}
        </p>
      )}

      <form onSubmit={handleGenerate} className="space-y-3">
        <div>
          <label className="block text-sm font-medium mb-1 text-ink" htmlFor="resource-type">
            What to generate
          </label>
          <select
            id="resource-type"
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            disabled={notReady || job.isRunning}
            className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
          >
            {RESOURCE_TYPES.map((entry) => (
              <option key={entry.type} value={entry.type}>
                {entry.label}
              </option>
            ))}
          </select>
        </div>

        <fieldset disabled={notReady || job.isRunning}>
          <legend className="block text-sm font-medium mb-1 text-ink">How much to read</legend>
          <div className="space-y-1">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="scope"
                value="passage"
                checked={scope === "passage"}
                onChange={() => setScope("passage")}
                className="mt-1 accent-ink"
              />
              <span>
                <span className="font-medium text-ink">One passage</span>
                <span className="block text-xs text-muted">
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
                className="mt-1 accent-ink"
              />
              <span>
                <span className="font-medium text-ink">The whole document</span>
                <span className="block text-xs text-muted">
                  Reads {pageCount ? `all ${pageCount} pages` : "every page"} in groups and pools
                  the results. Takes minutes, and is the only way to cover the whole PDF.
                </span>
              </span>
            </label>
          </div>
        </fieldset>

        {scope === "passage" && (
          <div>
            <label className="block text-sm font-medium mb-1 text-ink" htmlFor="topic">
              Topic <span className="font-normal text-muted">(optional)</span>
            </label>
            <input
              id="topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. directors' duties"
              disabled={notReady || job.isRunning}
              className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
            />
            <p className="text-xs text-muted mt-1">
              Picks the pages that best match. Left empty, the opening of the document is used.
            </p>
          </div>
        )}

        <div className="flex gap-3 items-end">
          {canUsePerPage && (
            <div>
              <label className="block text-sm font-medium mb-1 text-ink" htmlFor="amount-mode">
                Amount
              </label>
              <select
                id="amount-mode"
                value={amountMode}
                onChange={(e) => setAmountMode(e.target.value)}
                disabled={job.isRunning}
                className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
              >
                <option value="total">In total</option>
                <option value="per_page">Per page</option>
              </select>
            </div>
          )}

          <div className="flex-1">
            <label className="block text-sm font-medium mb-1 text-ink" htmlFor="amount">
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
              className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
            />
          </div>
        </div>

        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={evaluate}
            onChange={(e) => setEvaluate(e.target.checked)}
            disabled={notReady || job.isRunning}
            className="mt-1 accent-ink"
          />
          <span>
            <span className="text-ink">Review before showing</span>
            <span className="block text-xs text-muted">
              A second model grades the result and one retry is allowed. Turning this off is
              about twice as fast, and nothing checks what comes back.
            </span>
          </span>
        </label>

        <button
          type="submit"
          disabled={notReady || job.isRunning}
          className="w-full bg-ink text-white rounded-lg py-2 text-sm hover:bg-ink/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {job.isRunning ? "Generating..." : `Generate ${selectedType.label}`}
        </button>
      </form>

      <JobProgress job={job} className="mt-3" />

      {job.isDone && job.result && (
        <div className="mt-3 text-sm bg-verified-bg rounded-lg p-3">
          <Link to={`/resources/${job.result.id}`} className="text-ink hover:underline font-medium">
            View the {resourceLabel(job.result.resource_type)} →
          </Link>
          {job.result.requested && job.result.generated < job.result.requested && (
            <p className="text-xs text-muted mt-1">
              {job.result.generated} of the {job.result.requested} asked for — the document did
              not support more, or the rest repeated what was already there.
            </p>
          )}
        </div>
      )}

      <h4 className="font-medium text-sm mt-5 mb-2 text-ink">Already generated</h4>
      {loading ? (
        <p className="text-sm text-muted">Loading...</p>
      ) : resources.length === 0 ? (
        <p className="text-sm text-muted">Nothing yet for this document.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {resources.map((resource) => {
            const { tone, label } = qualityTone(resource);
            return (
              <li key={resource.id} className="py-2 flex justify-between items-center gap-2">
                <span className="text-sm min-w-0">
                  {resourceLabel(resource.resource_type)}
                  <span className="text-muted text-xs ml-2">
                    {new Date(resource.created_at).toLocaleString()}
                  </span>
                  <span className={`text-xs rounded-full px-2 py-0.5 ml-2 ${tone}`}>{label}</span>
                </span>
                <Link
                  to={`/resources/${resource.id}`}
                  className="text-sm text-ink font-medium hover:underline shrink-0"
                >
                  View
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default ResourcesPanel;
