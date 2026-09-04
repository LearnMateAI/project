/**
 * Upload a source file (PDF, Word, PowerPoint, or LaTeX).
 *
 * The shape of this follows the backend: the POST returns `202 {document, job_id}`, so
 * uploading is two phases with very different durations.
 *
 *   sending the bytes     seconds -- the progress bar
 *   processing the PDF    extract, clean, chunk, and a few thousand embeddings. Minutes --
 *                         the job, which reports what it is doing.
 *
 * The document row exists as soon as the first phase finishes, so it appears in the list
 * straight away as "Processing" whether or not this card is still on screen.
 *
 * Files arrive either from the picker or from a drop on the panel; both land in `handleFile`
 * so the size and type checks cannot be bypassed by dragging instead of clicking.
 */

import { useCallback, useEffect, useState } from "react";
import { listDocuments, uploadDocument } from "../api/documents.js";
import { useJob } from "../hooks/useJob.js";
import { MATTER_TYPES, setMatterType } from "../lib/matterTypes.js";
import JobProgress from "./JobProgress.jsx";

const SUBJECTS = [
  "Constitutional Law",
  "Law of Contract",
  "Criminal Law",
  "Law of Torts",
  "Property Law",
  "General",
];

// Matches LEARNMATE_MAX_PDF_MB in integrated-backend/.env. Kept in step deliberately:
// a browser limit looser than the server's just means the upload finishes and is then
// rejected, after the user has waited for it.
const MAX_MB = 10;
const SOURCE_EXTENSIONS = [".pdf", ".docx", ".pptx", ".tex"];

function fileExtension(name) {
  const lower = (name || "").toLowerCase();
  const dot = lower.lastIndexOf(".");
  return dot >= 0 ? lower.slice(dot) : "";
}

function DocumentsCard({ onUploaded }) {
  const [documentCount, setDocumentCount] = useState(null);
  const [subject, setSubject] = useState("General");
  const [matterKind, setMatterKind] = useState("case");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [progress, setProgress] = useState(0);
  const [sending, setSending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const job = useJob();

  const refreshCount = useCallback(async () => {
    try {
      const res = await listDocuments();
      setDocumentCount(res.data.length);
    } catch {
      setDocumentCount(null);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshCount();
  }, [refreshCount]);

  const busy = sending || job.isRunning;

  async function handleFile(file) {
    if (!file) return;

    setError("");
    setSuccess("");
    job.reset();

    // Checked here as well as on the server so an obviously wrong file costs nothing.
    // Extension, not MIME: Windows often sends an empty type or octet-stream for .docx / .tex.
    if (!SOURCE_EXTENSIONS.includes(fileExtension(file.name))) {
      setError("Upload a PDF, Word (.docx), PowerPoint (.pptx), or LaTeX (.tex) file.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`This file is ${(file.size / 1048576).toFixed(1)} MB, over the ${MAX_MB} MB limit.`);
      return;
    }

    setSending(true);
    setProgress(0);

    // Phase 1 and phase 2 in one call: `run` takes the function that produces the 202 and
    // then polls the job it names. It never throws -- a rejected upload and a failed job
    // both land in job.error, which JobProgress renders -- so there is nothing to catch.
    const result = await job.run(() =>
      uploadDocument({
        file,
        subject,
        onUploadProgress: (event) => {
          if (event.total) setProgress(Math.round((event.loaded * 100) / event.total));
        },
      }),
    );

    if (result) {
      const documentId = result.document_id || result.id;
      if (documentId) setMatterType(documentId, matterKind);
      setSuccess(
        result.skipped
          ? `"${file.name}" was already indexed — ready straight away.`
          : `"${file.name}" is ready: ${result.pages} extractable units, ${result.chunks} passages.`,
      );
      await refreshCount();
      onUploaded?.({ id: documentId, ...result });
    }

    setSending(false);
  }

  async function handleFileChange(e) {
    const file = e.target.files[0];
    await handleFile(file);
    e.target.value = "";
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    if (busy) return;
    handleFile(e.dataTransfer.files?.[0]);
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>File a source</h2>
          <p className="text-[12px] text-muted mt-0.5">
            {documentCount === null
              ? "Checking your library..."
              : documentCount === 0
                ? "No sources yet"
                : `${documentCount} source${documentCount === 1 ? "" : "s"} in your library`}
          </p>
        </div>
        <span className="icon-tile icon-tile-soft w-10 h-10">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
        </span>
      </div>

      <div className="card-body">
        <label className="field-label" htmlFor="matter-kind">
          File as
        </label>
        <select
          id="matter-kind"
          value={matterKind}
          onChange={(e) => setMatterKind(e.target.value)}
          disabled={busy}
          className="select mb-4"
        >
          {MATTER_TYPES.map((entry) => (
            <option key={entry.id} value={entry.id}>
              {entry.singular}
            </option>
          ))}
        </select>

        <label className="field-label" htmlFor="subject">
          Subject
        </label>
        <select
          id="subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          disabled={busy}
          className="select mb-4"
        >
          {SUBJECTS.map((entry) => (
            <option key={entry} value={entry}>
              {entry}
            </option>
          ))}
        </select>

        <label
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`block rounded-xl border border-dashed px-4 py-6 text-center cursor-pointer transition-colors ${
            busy
              ? "border-border bg-surface-alt cursor-not-allowed"
              : dragging
                ? "border-primary bg-primary-soft"
                : "border-border-strong hover:border-primary hover:bg-primary-soft"
          }`}
        >
          <input
            type="file"
            accept=".pdf,.docx,.pptx,.tex,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,text/x-tex,text/plain"
            onChange={handleFileChange}
            disabled={busy}
            className="sr-only"
          />
          <svg
            className={`w-7 h-7 mx-auto mb-2 ${dragging ? "text-primary" : "text-subtle"}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
          </svg>
          <p className="text-[13px] font-semibold text-heading">
            {busy ? "Working on it..." : "Drop a file here, or click to choose"}
          </p>
          <p className="text-[11.5px] text-subtle mt-0.5">
            PDF, Word (.docx), PowerPoint (.pptx), or LaTeX (.tex) · up to {MAX_MB} MB
          </p>
          <p className="text-[11.5px] text-muted mt-2 leading-relaxed max-w-sm mx-auto">
            Text is extracted the same way as a PDF: pages, slides, or sections are cleaned,
            chunked, and indexed so you can generate summaries and quizzes. Image-only
            scans or slides with no selectable text cannot be indexed. Older .doc / .ppt
            files need to be saved as .docx / .pptx first.
          </p>
        </label>

        {/* Phase 1: bytes going up. Only shown while it is actually happening -- once the
            server has the file, the interesting number is the job's. */}
        {sending && job.isRunning && progress < 100 && (
          <div className="mt-3">
            <div className="flex justify-between text-[11.5px] text-muted mb-1">
              <span>Uploading</span>
              <span className="tabular-nums">{progress}%</span>
            </div>
            <div className="track">
              <span style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {/* Phase 2: what the backend is doing with it. */}
        <JobProgress job={job} className="mt-3" />

        {error && <p className="notice notice-error mt-3">{error}</p>}
        {success && <p className="notice notice-success mt-3">{success}</p>}
      </div>
    </section>
  );
}

export default DocumentsCard;
