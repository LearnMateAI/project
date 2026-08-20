/**
 * The document library: upload and list on the left, viewer and generation panel on the
 * right.
 *
 * Upload is the same DocumentsCard the dashboard uses rather than a second implementation
 * of it. It polls its own count and reports its own job progress, so the only wiring here
 * is refreshing the table once a file has finished processing.
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
import DocumentsCard from "../components/DocumentsCard.jsx";
import EmptyState from "../components/EmptyState.jsx";
import ResourcesPanel from "../components/ResourcesPanel.jsx";

const POLL_MS = 3000;

const STATUS_STYLES = {
  Ready: "badge-green",
  Processing: "badge-blue",
  Uploaded: "badge-gray",
  "Failed Processing": "badge-red",
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

  const readyCount = documents.filter((doc) => doc.processing_status === "Ready").length;

  return (
    <div>
      <div className="flex flex-wrap justify-between items-end gap-3 mb-5">
        <div className="page-header mb-0">
          <h1>Your Documents</h1>
          <p>
            {documents.length === 0
              ? "Upload a PDF to build your study library"
              : `${documents.length} uploaded · ${readyCount} ready to use`}
          </p>
        </div>
        <button onClick={() => fetchDocuments()} className="btn-secondary">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992V4.356m-4.993 4.992l3.181-3.183a8.25 8.25 0 00-13.803 3.7M4.031 9.865v4.99m0 0h4.99m-4.99 0l3.181 3.183a8.25 8.25 0 0013.803-3.7" />
          </svg>
          Refresh
        </button>
      </div>

      {error && <p className="notice notice-error mb-4">{error}</p>}
      {notice && <p className="notice notice-info mb-4">{notice}</p>}

      <div className="grid gap-5 xl:grid-cols-2 items-start">
        {/* Left column: the documents you have, and the way to add another. Upload sits
            above the table it feeds, so a new row appears directly under the control that
            created it. The right column is for working with whichever one is selected, and
            keeping the two apart stops an upload card shifting the preview down the page. */}
        <div className="space-y-5">
          <DocumentsCard onUploaded={() => fetchDocuments({ quiet: true })} />

          <section className="card overflow-hidden">
            <div className="card-head">
              <h2>Library</h2>
              {anyProcessing && (
                <span className="badge badge-blue">
                  <span className="spinner w-3 h-3" />
                  Processing
                </span>
              )}
            </div>

            <div className="overflow-x-auto">
              {loading ? (
                <p className="px-5 py-6 text-[13px] text-muted">Loading documents...</p>
              ) : documents.length === 0 ? (
                <EmptyState
                  body="No documents yet — upload a PDF above to get started."
                  action={null}
                />
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Subject</th>
                      <th className="num">Pages</th>
                      <th className="num">Size</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc) => (
                      <tr
                        key={doc.id}
                        onClick={() => handleSelect(doc)}
                        className={`is-clickable ${selectedId === doc.id ? "is-selected" : ""}`}
                      >
                        <td className="font-medium text-heading max-w-[16rem] truncate" title={doc.filename}>
                          {doc.filename}
                        </td>
                        <td className="text-muted whitespace-nowrap">{doc.subject}</td>
                        <td className="num">{doc.page_count ?? "—"}</td>
                        <td className="num whitespace-nowrap">{formatSize(doc.file_size)}</td>
                        <td>
                          <span
                            className={`badge ${STATUS_STYLES[doc.processing_status] || "badge-gray"}`}
                            title={doc.processing_error || undefined}
                          >
                            <span className="badge-dot" />
                            {doc.processing_status}
                          </span>
                        </td>
                        <td className="num">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(doc);
                            }}
                            className="text-[12px] font-semibold text-muted hover:text-danger"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* A failed ingest has a reason, and it is usually actionable -- a scanned PDF
                needs OCR, an encrypted one needs an unprotected copy. Surface it. */}
            {documents
              .filter((doc) => doc.processing_status === "Failed Processing" && doc.processing_error)
              .map((doc) => (
                <p key={doc.id} className="notice notice-error mx-4 mb-4 text-[12px]">
                  <span className="font-semibold">{doc.filename}:</span> {doc.processing_error}
                </p>
              ))}
          </section>
        </div>

        <div className="space-y-5">
          <section className="card overflow-hidden">
            <div className="card-head">
              <h2 className="truncate">{selected ? selected.filename : "Preview"}</h2>
              {selected && (
                <span className="badge badge-gray shrink-0">
                  {selected.page_count ? `${selected.page_count} pages` : "PDF"}
                </span>
              )}
            </div>
            <div className="p-4">
              {!selected ? (
                <div className="h-[420px] rounded-xl border border-dashed border-border flex flex-col items-center justify-center gap-2 text-center px-6">
                  <svg className="w-8 h-8 text-subtle" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.4}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                  <p className="text-[13px] text-muted m-0">Select a document to read it here.</p>
                </div>
              ) : viewerLoading ? (
                <div className="h-[420px] flex items-center justify-center gap-2.5 text-[13px] text-muted">
                  <span className="spinner" />
                  Loading preview...
                </div>
              ) : pdfUrl ? (
                <iframe
                  src={pdfUrl}
                  title={selected.filename}
                  className="w-full h-[520px] rounded-xl border border-border"
                />
              ) : null}
            </div>
          </section>

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
