/**
 * One source, two ways to read it.
 *
 * PDF   the original layout -- what a court or lecturer issued.
 * Text  the cleaned page text the models actually read, set in a serif for long sessions.
 *
 * Both stay in the same pane so the split workspace does not lose the document when the
 * student switches from scanning a scanned judgment to reading the extracted text.
 */

import { useEffect, useState } from "react";
import { getDocumentPages } from "../api/documents.js";

function DocumentReader({ documentId, filename, pdfUrl, loading }) {
  const [mode, setMode] = useState("pdf");
  const [pages, setPages] = useState([]);
  const [textError, setTextError] = useState("");
  const [textLoading, setTextLoading] = useState(false);

  useEffect(() => {
    if (mode !== "text" || !documentId) return undefined;
    let cancelled = false;
    setTextLoading(true);
    setTextError("");
    getDocumentPages(documentId)
      .then((res) => {
        if (!cancelled) setPages(res.data || []);
      })
      .catch(() => {
        if (!cancelled) setTextError("Could not load the extracted text for this document.");
      })
      .finally(() => {
        if (!cancelled) setTextLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mode, documentId]);

  return (
    <div className="workspace-pane">
      <div className="card-head">
        <h2 className="truncate">{filename || "Source"}</h2>
        <div className="flex gap-1 shrink-0">
          <button
            type="button"
            className={`btn-ghost ${mode === "pdf" ? "text-heading" : ""}`}
            onClick={() => setMode("pdf")}
            aria-pressed={mode === "pdf"}
          >
            PDF
          </button>
          <button
            type="button"
            className={`btn-ghost ${mode === "text" ? "text-heading" : ""}`}
            onClick={() => setMode("text")}
            aria-pressed={mode === "text"}
          >
            Text
          </button>
        </div>
      </div>

      <div className="workspace-pane-body p-0">
        {loading ? (
          <div className="h-full min-h-[28rem] flex items-center justify-center gap-2.5 text-[13px] text-muted">
            <span className="spinner" />
            Loading preview...
          </div>
        ) : mode === "pdf" && pdfUrl ? (
          <iframe src={pdfUrl} title={filename} className="w-full h-full min-h-[28rem] border-0 bg-surface-alt" />
        ) : mode === "text" ? (
          <div className="paper h-full min-h-[28rem] px-5 py-6 sm:px-8 sm:py-7">
            {textLoading ? (
              <p className="font-sans text-[13px] text-muted m-0">Loading extracted text...</p>
            ) : textError ? (
              <p className="font-sans notice notice-error m-0">{textError}</p>
            ) : pages.length === 0 ? (
              <p className="font-sans text-[13px] text-muted m-0">
                No extracted text yet — image-only scans without a text layer cannot be indexed.
              </p>
            ) : (
              pages.map((page) => (
                <section key={page.page_number} className="mb-8">
                  <p className="font-sans text-[11px] font-semibold uppercase tracking-wider text-muted m-0 mb-2">
                    Page {page.page_number}
                  </p>
                  <p className="whitespace-pre-wrap m-0">{page.text}</p>
                </section>
              ))
            )}
          </div>
        ) : (
          <div className="h-full min-h-[28rem] flex items-center justify-center text-[13px] text-muted">
            Select a document to read it here.
          </div>
        )}
      </div>
    </div>
  );
}

export default DocumentReader;
