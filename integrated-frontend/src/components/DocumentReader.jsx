/**
 * One source, two ways to read it.
 *
 * PDF   the original layout -- what a court or lecturer issued.
 * Text  the cleaned page text the models actually read, set in a serif for long sessions.
 *
 * "Full window" expands the same pane over the viewport so a dense judgment is readable
 * without the split workspace crowding it.
 */

import { useEffect, useState } from "react";
import { getDocumentPages } from "../api/documents.js";

function unitSingular(label) {
  if (label === "slides") return "Slide";
  if (label === "sections") return "Section";
  return "Page";
}

function ReaderBody({
  loading, mode, pdfUrl, filename, textLoading, textError, pages, unitLabel,
  fillWindow,
}) {
  const fill = fillWindow ? "h-full min-h-0" : "h-full min-h-[28rem]";
  if (loading) {
    return (
      <div className={`${fill} flex items-center justify-center gap-2.5 text-[13px] text-muted`}>
        <span className="spinner" />
        Loading preview...
      </div>
    );
  }
  if (mode === "pdf" && pdfUrl) {
    return (
      <iframe
        src={pdfUrl}
        title={filename}
        className={`w-full ${fill} border-0 bg-surface-alt`}
      />
    );
  }
  if (mode === "text") {
    return (
      <div className={`paper ${fill} overflow-y-auto px-5 py-6 sm:px-8 sm:py-7`}>
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
                {unitSingular(unitLabel)} {page.page_number}
              </p>
              <p className="whitespace-pre-wrap m-0">{page.text}</p>
            </section>
          ))
        )}
      </div>
    );
  }
  return (
    <div className={`${fill} flex items-center justify-center text-[13px] text-muted`}>
      Select a document to read it here.
    </div>
  );
}

function DocumentReader({
  documentId,
  filename,
  pdfUrl,
  loading,
  sourceKind = "pdf",
  unitLabel = "pages",
}) {
  const isPdf = sourceKind === "pdf";
  const [mode, setMode] = useState(isPdf ? "pdf" : "text");
  const [pages, setPages] = useState([]);
  const [textError, setTextError] = useState("");
  const [textLoading, setTextLoading] = useState(false);
  const [fullWindow, setFullWindow] = useState(false);

  useEffect(() => {
    setMode(isPdf ? "pdf" : "text");
    setPages([]);
    setFullWindow(false);
  }, [documentId, isPdf]);

  useEffect(() => {
    if (!fullWindow) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") setFullWindow(false);
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [fullWindow]);

  useEffect(() => {
    if (mode !== "text" || !documentId) return undefined;
    let cancelled = false;
    // Fetch triggered by a mode switch, not a render. The rule guards against cascading
    // renders from derived state; this is a request to an external system, which is what
    // an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
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

  const modeButtons = (
    <div className="flex gap-1 shrink-0">
      {isPdf && (
        <button
          type="button"
          className={`btn-ghost ${mode === "pdf" ? "text-heading" : ""}`}
          onClick={() => setMode("pdf")}
          aria-pressed={mode === "pdf"}
        >
          PDF
        </button>
      )}
      <button
        type="button"
        className={`btn-ghost ${mode === "text" ? "text-heading" : ""}`}
        onClick={() => setMode("text")}
        aria-pressed={mode === "text"}
      >
        Text
      </button>
      <button
        type="button"
        className="btn-ghost"
        onClick={() => setFullWindow((open) => !open)}
        aria-pressed={fullWindow}
      >
        {fullWindow ? "Exit full window" : "Full window"}
      </button>
    </div>
  );

  const body = (
    <ReaderBody
      loading={loading}
      mode={mode}
      pdfUrl={pdfUrl}
      filename={filename}
      textLoading={textLoading}
      textError={textError}
      pages={pages}
      unitLabel={unitLabel}
      fillWindow={fullWindow}
    />
  );

  return (
    <>
      <div className="workspace-pane">
        <div className="card-head">
          <h2 className="truncate">{filename || "Source"}</h2>
          {modeButtons}
        </div>
        <div className="workspace-pane-body p-0">{body}</div>
      </div>

      {fullWindow && (
        <div className="document-reader-overlay" role="dialog" aria-modal="true" aria-label={filename || "Source"}>
          <div className="card-head">
            <h2 className="truncate">{filename || "Source"}</h2>
            {modeButtons}
          </div>
          <div className="document-reader-overlay-body">{body}</div>
        </div>
      )}
    </>
  );
}

export default DocumentReader;
