/**
 * Everything this user has generated, newest first.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client.js";
import { listDocuments } from "../../api/documents.js";
import { RESOURCE_TYPES, listResources, resourceLabel } from "../../api/resources.js";
import { qualityTone } from "../../components/QualityBadge.jsx";

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
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchResources();
  }, [fetchResources]);

  useEffect(() => {
    listDocuments()
      .then((res) => setDocuments(res.data))
      .catch(() => setDocuments([]));
  }, []);

  const filenames = useMemo(
    () => Object.fromEntries(documents.map((doc) => [doc.id, doc.filename])),
    [documents],
  );

  return (
    <div>
      <h1 className="font-display text-2xl font-bold mb-6 text-ink">Your Resources</h1>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white"
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
          className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white"
        >
          <option value="">All types</option>
          {RESOURCE_TYPES.map((entry) => (
            <option key={entry.type} value={entry.type}>
              {entry.label}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-danger mb-4">{error}</p>}

      <div className="bg-white rounded-xl border border-gray-100 p-4">
        {loading ? (
          <p className="text-sm text-muted">Loading...</p>
        ) : resources.length === 0 ? (
          <p className="text-sm text-muted">
            Nothing generated yet — open a document and use the panel beside it.
          </p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {resources.map((resource) => {
              const { tone, label } = qualityTone(resource);
              return (
                <li key={resource.id} className="py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <Link
                      to={`/resources/${resource.id}`}
                      className="text-sm font-medium text-ink hover:underline"
                    >
                      {resourceLabel(resource.resource_type)}
                    </Link>
                    <p className="text-xs text-muted truncate">
                      {filenames[resource.document_id] || "Unknown document"} ·{" "}
                      {new Date(resource.created_at).toLocaleString()}
                      {Array.isArray(resource.content) ? ` · ${resource.content.length} items` : ""}
                    </p>
                  </div>

                  <span className={`text-xs rounded-full px-2.5 py-1 font-medium shrink-0 ${tone}`}>
                    {label}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default Resources;
