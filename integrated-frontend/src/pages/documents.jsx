/**
 * The case library and split-screen workspace.
 *
 * Upload and the filing list stay on this route (`/documents` in the SRS). Selecting a
 * source opens a workspace: the PDF (or cleaned text) on one side, generate / ask on the
 * other, so a student does not tab away from a dense judgment to use the model.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client.js";
import { deleteDocument, getDocumentFile, listDocuments } from "../api/documents.js";
import DocumentReader from "../components/DocumentReader.jsx";
import DocumentsCard from "../components/DocumentsCard.jsx";
import ResourcesPanel from "../components/ResourcesPanel.jsx";
import WorkspaceChat from "../components/WorkspaceChat.jsx";

const POLL_MS = 3000;

const STATUS_STYLES = {
  Ready: "badge-green",
  Processing: "badge-blue",
  Uploaded: "badge-gray",
  "Failed Processing": "badge-red",
};

// One cover tint per subject, drawn from the existing palette tokens rather than new
// colours -- a document's subject is the one thing worth telling apart at a glance on a
// shelf of otherwise-identical PDFs.
const SUBJECT_TINTS = {
  "Constitutional Law": "var(--color-primary)",
  "Law of Contract": "var(--color-violet)",
  "Criminal Law": "var(--color-cyan)",
  "Law of Torts": "var(--color-accent)",
  "Property Law": "var(--color-success)",
  General: "var(--color-subtle)",
};
const DEFAULT_TINT = "var(--color-muted)";

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
  const [workspaceTab, setWorkspaceTab] = useState("generate");
  const pdfUrlRef = useRef(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const openedFromLinkRef = useRef(false);

  const fetchDocuments = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const res = await listDocuments();
      setDocuments(res.data);
      setError("");
    } catch (err) {
      setError(errorMessage(err, "Could not load your library."));
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

  const anyProcessing = documents.some(
    (doc) => doc.processing_status === "Processing" || doc.processing_status === "Uploaded",
  );

  useEffect(() => {
    if (!anyProcessing) return undefined;
    const timer = setInterval(() => fetchDocuments({ quiet: true }), POLL_MS);
    return () => clearInterval(timer);
  }, [anyProcessing, fetchDocuments]);

  useEffect(
    () => () => {
      if (pdfUrlRef.current) URL.revokeObjectURL(pdfUrlRef.current);
    },
    [],
  );

  // Deep link from the dashboard's "Split-screen workspace" card (?open=<id>): jump
  // straight into that document's workspace instead of the library list. Runs once the
  // matching row has loaded, and only once -- the ref stops it firing again after the
  // student navigates back to the library while the param is still in the URL.
  useEffect(() => {
    if (openedFromLinkRef.current) return;
    const openId = searchParams.get("open");
    if (!openId) return;
    const doc = documents.find((entry) => entry.id === openId);
    if (!doc) return;
    openedFromLinkRef.current = true;
    handleSelect(doc);
    setSearchParams((params) => {
      params.delete("open");
      return params;
    }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents, searchParams]);

  const selected = documents.find((doc) => doc.id === selectedId) || null;
  async function handleSelect(doc) {
    setSelectedId(doc.id);
    setNotice("");
    setWorkspaceTab("generate");

    if (pdfUrlRef.current) {
      URL.revokeObjectURL(pdfUrlRef.current);
      pdfUrlRef.current = null;
    }
    setPdfUrl(null);
    setViewerLoading(true);

    const kind = doc.source_kind || "pdf";
    if (kind !== "pdf") {
      setViewerLoading(false);
      return;
    }

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
    if (!window.confirm(`Remove "${doc.filename}" from your library?`)) return;
    try {
      const res = await deleteDocument(doc.id);
      setNotice(
        res.data.purged
          ? `"${doc.filename}" was deleted.`
          : `"${doc.filename}" was removed from your library. The file itself is kept because another account also has it.`,
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
          <h1>Library</h1>
          <p>
            {documents.length === 0
              ? "Upload a PDF, Word, PowerPoint, or LaTeX document"
              : `${documents.length} filed · ${readyCount} ready`}
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

      {selected ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="btn-secondary" onClick={() => setSelectedId(null)}>
              ← Library
            </button>
            <select
              className="select w-auto min-w-[14rem]"
              value={selected.id}
              onChange={(e) => {
                const next = documents.find((doc) => doc.id === e.target.value);
                if (next) handleSelect(next);
              }}
              aria-label="Switch source"
            >
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
            <span className="badge badge-gray">
              {selected.page_count
                ? `${selected.page_count} ${selected.unit_label || "pages"}`
                : (selected.source_kind || "pdf").toUpperCase()}
            </span>
          </div>

          <div className="workspace-split">
            <DocumentReader
              key={`${selected.id}-${selected.source_kind || "pdf"}`}
              documentId={selected.id}
              filename={selected.filename}
              pdfUrl={pdfUrl}
              loading={viewerLoading}
              sourceKind={selected.source_kind || "pdf"}
              unitLabel={selected.unit_label || "pages"}
            />

            <div className="workspace-pane">
              <div className="tab-bar">
                <button
                  type="button"
                  className={`tab-btn ${workspaceTab === "generate" ? "is-active" : ""}`}
                  onClick={() => setWorkspaceTab("generate")}
                >
                  Study material
                </button>
                <button
                  type="button"
                  className={`tab-btn ${workspaceTab === "ask" ? "is-active" : ""}`}
                  onClick={() => setWorkspaceTab("ask")}
                >
                  Ask the record
                </button>
              </div>
              <div className="workspace-pane-body">
                <div hidden={workspaceTab !== "generate"} className={workspaceTab === "generate" ? "" : "hidden"}>
                  <div className="p-3">
                    <ResourcesPanel
                      documentId={selected.id}
                      documentStatus={selected.processing_status}
                      pageCount={selected.page_count}
                    />
                  </div>
                </div>
                <div hidden={workspaceTab !== "ask"} className={workspaceTab === "ask" ? "h-full" : "hidden"}>
                  <WorkspaceChat
                    documentId={selected.id}
                    ready={selected.processing_status === "Ready"}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-5 xl:grid-cols-2 items-start">
          <div className="space-y-5">
            <DocumentsCard onUploaded={() => fetchDocuments({ quiet: true })} />
          </div>

          <div>
            <div className="flex items-center justify-between gap-3 mb-3">
              <h2 className="section-title mb-0">Library</h2>
              {anyProcessing && (
                <span className="badge badge-blue">
                  <span className="spinner w-3 h-3" />
                  Processing
                </span>
              )}
            </div>

            {loading ? (
              <p className="card px-5 py-6 text-[13px] text-muted">Loading documents...</p>
            ) : documents.length === 0 ? (
              <p className="card px-5 py-6 text-[13px] text-muted">
                No documents yet — upload a file above to get started.
              </p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {/* The shelf: each PDF is a cover tinted by subject rather than a row in a
                    table, so the library reads as a set of books rather than a spreadsheet. */}
                {documents.map((doc) => {
                  const tint = SUBJECT_TINTS[doc.subject] || DEFAULT_TINT;
                  return (
                    <div
                      key={doc.id}
                      onClick={() => handleSelect(doc)}
                      className={`book-tile cursor-pointer ${selectedId === doc.id ? "is-selected" : ""}`}
                    >
                      <div
                        className="book-cover"
                        style={{
                          backgroundImage: `linear-gradient(150deg, ${tint} 0%, color-mix(in srgb, ${tint} 70%, black) 100%)`,
                        }}
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="#fff" strokeWidth={1.6}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                        </svg>
                        <span className="text-[10px] font-bold text-white/75 tracking-[0.04em] uppercase truncate">
                          {doc.subject}
                        </span>
                      </div>
                      <div className="book-tile-body">
                        <p
                          className="text-[13px] font-semibold text-heading mb-1.5 truncate"
                          title={doc.filename}
                        >
                          {doc.filename}
                        </p>
                        <p className="text-[11px] text-subtle mb-2.5">
                          {doc.page_count
                            ? `${doc.page_count} ${doc.unit_label || "pages"}`
                            : (doc.source_kind || "pdf").toUpperCase()} · {formatSize(doc.file_size)}
                        </p>
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className={`badge ${STATUS_STYLES[doc.processing_status] || "badge-gray"}`}
                            title={doc.processing_error || undefined}
                          >
                            <span className="badge-dot" />
                            {doc.processing_status}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(doc);
                            }}
                            className="text-[11.5px] font-semibold text-muted hover:text-danger"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {documents
              .filter((doc) => doc.processing_status === "Failed Processing" && doc.processing_error)
              .map((doc) => (
                <p key={doc.id} className="notice notice-error mt-4 text-[12px]">
                  <span className="font-semibold">{doc.filename}:</span> {doc.processing_error}
                </p>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default Documents;
