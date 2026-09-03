/**
 * Everything this user has generated, newest first.
 *
 * Rejected resources are listed alongside accepted ones. That is what the backend stores
 * and what the evaluation log counts, and filtering them out here would quietly hide the
 * failure rate from the person best placed to notice it.
 *
 * The list itself is deliberately quiet about scores -- what a row is, which PDF it came
 * from, and when. The reviewer's verdict lives on the resource's own page, where the
 * reasoning that goes with it is also on screen; a number in a list invites comparison
 * without any of the context that makes it mean something.
 *
 * Generations still running are listed above the finished ones, read from the job queue
 * rather than from the resources themselves -- a resource does not exist in the database
 * until its job completes, so without this the page looked empty for the several minutes
 * it takes to fill.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client.js";
import { listDocuments } from "../../api/documents.js";
import { listJobs } from "../../api/jobs.js";
import { RESOURCE_TYPES, listResources, resourceLabel } from "../../api/resources.js";
import EmptyState from "../../components/EmptyState.jsx";

// A generation runs for minutes, and its own commentary changes about once a page. Only
// polled while something is actually in flight -- see the effect below, which stops.
const POLL_MS = 3000;

function Resources() {
  const [resources, setResources] = useState([]);
  const [pending, setPending] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchResources = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const res = await listResources({
        documentId: documentId || undefined,
        resourceType: resourceType || undefined,
      });
      setResources(res.data);
      setError("");
    } catch (err) {
      setError(errorMessage(err, "Could not load your resources."));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, [documentId, resourceType]);

  /**
   * Generations that have not finished yet.
   *
   * A resource is only written to the database once its job completes, so until then it is
   * nowhere in listResources and the page looked idle while the machine was busy for
   * minutes. The job queue does know about it, so that is what is read here: every resource
   * job, narrowed to the ones still queued or running.
   *
   * Filtered client-side rather than by asking twice, because the endpoint takes one status
   * at a time and this is one short list either way.
   */
  const fetchPending = useCallback(async () => {
    try {
      const res = await listJobs({ kind: "resource" });
      setPending(
        res.data.filter((job) => {
          if (job.status !== "queued" && job.status !== "running") return false;
          // The page's own filters apply to pending rows too; a row that ignored them
          // would look like the filter had failed.
          const params = job.params || {};
          if (documentId && params.document_id !== documentId) return false;
          if (resourceType && params.resource_type !== resourceType) return false;
          return true;
        }),
      );
    } catch {
      // The list is still useful without it, and a failure here must not replace the page
      // with an error about something that is only decoration until it finishes.
      setPending([]);
    }
  }, [documentId, resourceType]);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchResources();
    fetchPending();
  }, [fetchResources, fetchPending]);

  // Re-poll only while something is in flight, and stop the moment nothing is.
  useEffect(() => {
    if (pending.length === 0) return undefined;
    const timer = setInterval(fetchPending, POLL_MS);
    return () => clearInterval(timer);
  }, [pending.length, fetchPending]);

  // When a job leaves the pending list it has finished, and the resource it produced is now
  // in the database -- so this is the moment to go and fetch it. Quietly: the list is
  // already on screen and should gain a row, not blink through a loading state.
  const previousPending = useRef(0);
  useEffect(() => {
    if (pending.length < previousPending.current) {
      fetchResources({ quiet: true });
    }
    previousPending.current = pending.length;
  }, [pending.length, fetchResources]);

  useEffect(() => {
    listDocuments()
      .then((res) => setDocuments(res.data))
      .catch(() => setDocuments([]));
  }, []);

  // Resources carry a document id, not a filename, so the lookup happens here.
  const filenames = useMemo(
    () => Object.fromEntries(documents.map((doc) => [doc.id, doc.filename])),
    [documents],
  );

  const typeIcon = {
    summary: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z",
    keypoints: "M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z",
    mcq: "M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.746 3.746 0 0121 12z",
    practice_qsn: "M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z",
  };

  return (
    <div>
      <div className="page-header">
        <h1>Study materials</h1>
        <p>IRAC briefs, flashcards, MCQs and practice questions — newest first</p>
      </div>

      {/* Filters in one row above the list, which is where a filter belongs. */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          aria-label="Filter by source"
          className="select w-auto min-w-[12rem]"
        >
          <option value="">All sources</option>
          {documents.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {doc.filename}
            </option>
          ))}
        </select>

        <select
          value={resourceType}
          onChange={(e) => setResourceType(e.target.value)}
          aria-label="Filter by type"
          className="select w-auto min-w-[10rem]"
        >
          <option value="">All types</option>
          {RESOURCE_TYPES.map((entry) => (
            <option key={entry.type} value={entry.type}>
              {entry.label}
            </option>
          ))}
        </select>

        {(documentId || resourceType) && (
          <button
            onClick={() => {
              setDocumentId("");
              setResourceType("");
            }}
            className="btn-ghost"
          >
            Clear filters
          </button>
        )}
      </div>

      {error && <p className="notice notice-error mb-4">{error}</p>}

      <section className="card overflow-hidden">
        {loading ? (
          <p className="px-5 py-6 text-[13px] text-muted flex items-center gap-2.5">
            <span className="spinner" />
            Loading...
          </p>
        ) : resources.length === 0 && pending.length === 0 ? (
          <EmptyState
            title="No materials yet"
            body="Generate from a source — open the library and use the panel beside the PDF."
            action={
              <Link to="/documents" className="btn-primary">
                Open library
              </Link>
            }
          />
        ) : (
          <div>
            {/* In-flight generations, above the finished ones because they are newer than
                anything below and because this is the half of the page a waiting user is
                actually watching. Not links: there is nothing to open yet. */}
            {pending.map((job) => (
              <div key={job.id} className="list-row bg-primary-soft/40">
                <span className="flex items-center gap-3.5 min-w-0">
                  <span className="icon-tile icon-tile-soft w-10 h-10">
                    <span className="spinner" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[13.5px] font-semibold text-heading">
                      {resourceLabel(job.params?.resource_type, job.params)}
                    </span>
                    <span className="block text-[11.5px] text-muted truncate">
                      {filenames[job.params?.document_id] || "Unknown document"} ·{" "}
                      {/* The engine's own commentary while it runs -- "Generating...",
                          "Evaluating...", "Group 2/5: ..." -- which is the only honest
                          answer to "how far along is it" for a job with no percentage. */}
                      {job.status === "queued"
                        ? "Waiting to start"
                        : job.progress?.message || "Working..."}
                    </span>
                  </span>
                </span>
                <span className="badge badge-blue shrink-0">
                  <span className="badge-dot" />
                  {job.status === "queued" ? "Queued" : "Generating"}
                </span>
              </div>
            ))}

            {resources.map((resource) => (
              <Link key={resource.id} to={`/resources/${resource.id}`} className="list-row">
                <span className="flex items-center gap-3.5 min-w-0">
                  <span className="icon-tile icon-tile-soft w-10 h-10">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={typeIcon[resource.resource_type] || typeIcon.summary}
                      />
                    </svg>
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[13.5px] font-semibold text-heading">
                      {resourceLabel(resource.resource_type, resource.params)}
                      {Array.isArray(resource.content) ? (
                        <span className="font-normal text-muted"> · {resource.content.length} items</span>
                      ) : null}
                      {resource.params?.difficulty ? (
                        <span className="badge badge-gray ml-2">{resource.params.difficulty}</span>
                      ) : null}
                    </span>
                    <span className="block text-[11.5px] text-subtle truncate">
                      {filenames[resource.document_id] || "Unknown document"} ·{" "}
                      {new Date(resource.created_at).toLocaleString()}
                    </span>
                  </span>
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default Resources;
