/**
 * Everything this user has generated, newest first.
 *
 * Rejected resources are listed alongside accepted ones, marked. That is what the backend
 * stores and what the evaluation log counts, and filtering them out here would quietly
 * hide the failure rate from the person best placed to notice it.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client.js";
import { listDocuments } from "../../api/documents.js";
import { RESOURCE_TYPES, listResources, resourceLabel } from "../../api/resources.js";

function Resources() {
  const [resources, setResources] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchResources = useCallback(async () => {
    setLoading(true);
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
      setLoading(false);
    }
  }, [documentId, resourceType]);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchResources();
  }, [fetchResources]);

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
        <h1>Your Resources</h1>
        <p>Everything you have generated, newest first — including what the reviewer flagged</p>
      </div>

      {/* Filters in one row above the list, which is where a filter belongs. */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          aria-label="Filter by document"
          className="select w-auto min-w-[12rem]"
        >
          <option value="">All documents</option>
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
        ) : resources.length === 0 ? (
          <p className="px-5 py-8 text-[13px] text-muted text-center">
            Nothing generated yet — open a document and use the panel beside it.
          </p>
        ) : (
          <div>
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
                      {resourceLabel(resource.resource_type)}
                      {Array.isArray(resource.content) ? (
                        <span className="font-normal text-muted"> · {resource.content.length} items</span>
                      ) : null}
                    </span>
                    <span className="block text-[11.5px] text-subtle truncate">
                      {filenames[resource.document_id] || "Unknown document"} ·{" "}
                      {new Date(resource.created_at).toLocaleString()}
                    </span>
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
                  <span className="badge-dot" />
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
  );
}

export default Resources;
