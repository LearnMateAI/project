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
import EmptyState from "../components/EmptyState.jsx";
import ResourcesPanel from "../components/ResourcesPanel.jsx";
import WorkspaceChat from "../components/WorkspaceChat.jsx";
import { MATTER_TYPES, getMatterType, matterLabel, setMatterType } from "../lib/matterTypes.js";

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
  const [matterFilter, setMatterFilter] = useState("");
  const [workspaceTab, setWorkspaceTab] = useState("generate");
  const [matterVersion, setMatterVersion] = useState(0);
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
  const visible = matterFilter
    ? documents.filter((doc) => getMatterType(doc.id) === matterFilter)
    : documents;

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
      setMatterType(doc.id, "");
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

  function handleMatterChange(docId, kind) {
    setMatterType(docId, kind);
    setMatterVersion((value) => value + 1);
  }

  const readyCount = documents.filter((doc) => doc.processing_status === "Ready").length;

  return (
    <div>
      <div className="flex flex-wrap justify-between items-end gap-3 mb-5">
        <div className="page-header mb-0">
          <h1>Library</h1>
          <p>
            {documents.length === 0
              ? "File a PDF — cases, statutes, outlines, or briefs"
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
            <select
              className="select w-auto"
              value={getMatterType(selected.id)}
              onChange={(e) => handleMatterChange(selected.id, e.target.value)}
              aria-label="Matter type"
            >
              <option value="">Unfiled</option>
              {MATTER_TYPES.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.singular}
                </option>
              ))}
            </select>
            <span className="badge badge-gray">
              {selected.page_count ? `${selected.page_count} pages` : "PDF"}
            </span>
          </div>

          <div className="workspace-split">
            <DocumentReader
              documentId={selected.id}
              filename={selected.filename}
              pdfUrl={pdfUrl}
              loading={viewerLoading}
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

          <section className="card overflow-hidden">
            <div className="card-head">
              <h2>Filed sources</h2>
              {anyProcessing && (
                <span className="badge badge-blue">
                  <span className="spinner w-3 h-3" />
                  Processing
                </span>
              )}
            </div>

            <div className="px-4 pt-3 chip-row">
              <button
                type="button"
                className={`cite ${!matterFilter ? "cite-page" : ""}`}
                onClick={() => setMatterFilter("")}
              >
                All
              </button>
              {MATTER_TYPES.map((entry) => (
                <button
                  key={entry.id}
                  type="button"
                  className={`cite ${matterFilter === entry.id ? "cite-page" : ""}`}
                  onClick={() => setMatterFilter(entry.id)}
                >
                  {entry.label}
                </button>
              ))}
            </div>

            <div className="overflow-x-auto">
              {loading ? (
                <p className="px-5 py-6 text-[13px] text-muted">Loading library...</p>
              ) : visible.length === 0 ? (
                <EmptyState
                  body={
                    documents.length === 0
                      ? "No sources yet — file a PDF to the left to get started."
                      : "Nothing filed under this type yet."
                  }
                  action={null}
                />
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Type</th>
                      <th>Subject</th>
                      <th className="num">Pages</th>
                      <th className="num">Size</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((doc) => (
                      <tr
                        key={doc.id}
                        onClick={() => handleSelect(doc)}
                        className={`is-clickable ${selectedId === doc.id ? "is-selected" : ""}`}
                      >
                        <td className="font-medium text-heading max-w-[16rem] truncate" title={doc.filename}>
                          {doc.filename}
                        </td>
                        <td className="text-muted whitespace-nowrap">
                          {matterLabel(getMatterType(doc.id))}
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

            {documents
              .filter((doc) => doc.processing_status === "Failed Processing" && doc.processing_error)
              .map((doc) => (
                <p key={doc.id} className="notice notice-error mx-4 mb-4 text-[12px]">
                  <span className="font-semibold">{doc.filename}:</span> {doc.processing_error}
                </p>
              ))}
          </section>
        </div>
      )}
      {/* matterVersion forces the type column to refresh after a localStorage write. */}
      <span className="sr-only" aria-hidden="true">{matterVersion}</span>
    </div>
  );
}

export default Documents;
