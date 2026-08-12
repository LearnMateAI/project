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

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Your Resources</h1>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          className="border rounded px-2 py-1.5 text-sm bg-white"
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
          className="border rounded px-2 py-1.5 text-sm bg-white"
        >
          <option value="">All types</option>
          {RESOURCE_TYPES.map((entry) => (
            <option key={entry.type} value={entry.type}>
              {entry.label}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="bg-white rounded-lg shadow-sm p-4">
        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : resources.length === 0 ? (
          <p className="text-sm text-gray-500">
            Nothing generated yet — open a document and use the panel beside it.
          </p>
        ) : (
          <ul className="divide-y">
            {resources.map((resource) => (
              <li key={resource.id} className="py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <Link
                    to={`/resources/${resource.id}`}
                    className="text-sm font-medium text-blue-600 hover:underline"
                  >
                    {resourceLabel(resource.resource_type)}
                  </Link>
                  <p className="text-xs text-gray-500 truncate">
                    {filenames[resource.document_id] || "Unknown document"} ·{" "}
                    {new Date(resource.created_at).toLocaleString()}
                    {Array.isArray(resource.content) ? ` · ${resource.content.length} items` : ""}
                  </p>
                </div>

                <span
                  className={`text-xs rounded px-2 py-1 shrink-0 ${
                    resource.score === null || resource.score === undefined
                      ? "bg-gray-100 text-gray-600"
                      : resource.accepted
                        ? "bg-green-100 text-green-700"
                        : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {resource.score === null || resource.score === undefined
                    ? "Not reviewed"
                    : `${resource.score}/100`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default Resources;
