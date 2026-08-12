/**
 * The document library: list on the left, viewer and generation panel on the right.
 *
 * The one behaviour worth knowing: while any row is still `Processing`, the list re-polls
 * every few seconds and stops as soon as none are. Ingestion runs on the job queue, so a
 * row that says Processing becomes Ready on its own -- without this the user would be
 * pressing Refresh to find out, which is exactly the thing a status column is supposed to
 * save them from.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client.js";
import { deleteDocument, getDocumentFile, listDocuments } from "../api/documents.js";
import ResourcesPanel from "../components/ResourcesPanel.jsx";

const POLL_MS = 3000;

const STATUS_STYLES = {
  Ready: "bg-green-100 text-green-700",
  Processing: "bg-blue-100 text-blue-700",
  Uploaded: "bg-gray-100 text-gray-600",
  "Failed Processing": "bg-red-100 text-red-700",
};

function formatSize(bytes) {
  if (!bytes) return "—";
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function Documents() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const pdfUrlRef = useRef(null);

  const fetchDocuments = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const res = await listDocuments();
      setDocuments(res.data);
      setError("");
    } catch (err) {
      setError(errorMessage(err, "Could not load documents."));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDocuments();
  }, [fetchDocuments]);

  // Re-poll only while something is actually in flight, and stop the moment it is not.
  const anyProcessing = documents.some(
    (doc) => doc.processing_status === "Processing" || doc.processing_status === "Uploaded",
  );

  useEffect(() => {
    if (!anyProcessing) return undefined;
    const timer = setInterval(() => fetchDocuments({ quiet: true }), POLL_MS);
    return () => clearInterval(timer);
  }, [anyProcessing, fetchDocuments]);

  // One object URL alive at a time, revoked when it is replaced and on unmount. Blob URLs
  // hold the whole PDF in memory until revoked, and clicking through ten documents would
  // otherwise keep all ten.
  useEffect(
    () => () => {
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
    },
    [],
  );

  const selected = documents.find((doc) => doc.id === selectedId) || null;

  async function handleSelect(doc) {
    setSelectedId(doc.id);
    setNotice("");

    if (pdfUrlRef.current) {
      URL.revokeObjectURL(pdfUrlRef.current);
      pdfUrlRef.current = null;
    }
    setPdfUrl(null);
    setViewerLoading(true);

    try {
      const res = await getDocumentFile(doc.id);
      const blobUrl = URL.createObjectURL(res.data);
      pdfUrlRef.current = blobUrl;
      setPdfUrl(blobUrl);
    } catch {
      setError("Could not load this document. Please try again.");
    } finally {
      setViewerLoading(false);
    }
  }

  async function handleDelete(doc) {
    if (!window.confirm(`Remove "${doc.filename}" from your documents?`)) return;
    try {
      const res = await deleteDocument(doc.id);
      // `purged: false` means somebody else uploaded the same file. Worth saying, because
      // "deleted" and "removed from your list" are different things and the second one is
      // what actually happened.
      setNotice(
        res.data.purged
          ? `"${doc.filename}" was deleted.`
          : `"${doc.filename}" was removed from your documents. The file itself is kept because another account also has it.`,
      );
      if (selectedId === doc.id) {
        setSelectedId(null);
        setPdfUrl(null);
      }
      await fetchDocuments({ quiet: true });
    } catch (err) {
      setError(errorMessage(err, "Could not delete this document."));
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold">Your Documents</h1>
        <button onClick={() => fetchDocuments()} className="text-sm text-blue-600 hover:underline">
          Refresh
        </button>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}
      {notice && <p className="text-sm text-gray-600 mb-4">{notice}</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="bg-white rounded-lg shadow-sm p-4 overflow-x-auto">
          {loading ? (
            <p className="text-sm text-gray-500">Loading documents...</p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-gray-500">
              No documents yet — upload one from the Dashboard to get started.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="pb-2">Filename</th>
                  <th className="pb-2">Subject</th>
                  <th className="pb-2">Pages</th>
                  <th className="pb-2">Size</th>
                  <th className="pb-2">Chunks</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr
                    key={doc.id}
                    onClick={() => handleSelect(doc)}
                    className={`cursor-pointer border-b hover:bg-gray-50 ${
                      selectedId === doc.id ? "bg-blue-50" : ""
                    }`}
                  >
                    <td className="py-2 pr-2">{doc.filename}</td>
                    <td className="py-2 pr-2">{doc.subject}</td>
                    <td className="py-2 pr-2">{doc.page_count ?? "—"}</td>
                    <td className="py-2 pr-2">{formatSize(doc.file_size)}</td>
                    <td className="py-2 pr-2">{doc.chunk_count || "—"}</td>
                    <td className="py-2 pr-2">
                      <span
                        className={`text-xs rounded px-2 py-1 whitespace-nowrap ${
                          STATUS_STYLES[doc.processing_status] || "bg-gray-100 text-gray-600"
                        }`}
                        title={doc.processing_error || undefined}
                      >
                        {doc.processing_status}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(doc);
                        }}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* A failed ingest has a reason, and it is usually actionable -- a scanned PDF
              needs OCR, an encrypted one needs an unprotected copy. Surface it. */}
          {documents
            .filter((doc) => doc.processing_status === "Failed Processing" && doc.processing_error)
            .map((doc) => (
              <p key={doc.id} className="text-xs text-red-600 mt-3">
                <span className="font-medium">{doc.filename}:</span> {doc.processing_error}
              </p>
            ))}
        </div>

        <div>
          <div className="bg-white rounded-lg shadow-sm p-4 min-h-[400px] flex items-center justify-center">
            {!selected ? (
              <p className="text-sm text-gray-400">Select a document to view it here.</p>
            ) : viewerLoading ? (
              <p className="text-sm text-gray-500">Loading preview...</p>
            ) : pdfUrl ? (
              <iframe src={pdfUrl} title={selected.filename} className="w-full h-[500px] rounded border" />
            ) : null}
          </div>

          {selected && (
            <ResourcesPanel
              documentId={selected.id}
              documentStatus={selected.processing_status}
              pageCount={selected.page_count}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default Documents;
