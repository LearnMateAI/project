/**
 * Upload a PDF.
 *
 * The shape of this changed with the backend: the POST returns `202 {document, job_id}`,
 * so uploading is now two phases with very different durations.
 *
 *   sending the bytes     seconds -- the progress bar
 *   processing the PDF    extract, clean, chunk, and a few thousand embeddings on CPU.
 *                         Minutes -- the job, which reports what it is doing.
 *
 * The document row exists as soon as the first phase finishes, so it appears in the list
 * straight away as "Processing" whether or not this card is still on screen.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { listDocuments, uploadDocument } from "../api/documents.js";
import { useJob } from "../hooks/useJob.js";
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

function DocumentsCard({ onUploaded }) {
  const [documentCount, setDocumentCount] = useState(null);
  const [subject, setSubject] = useState("General");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [progress, setProgress] = useState(0);
  const [sending, setSending] = useState(false);
  const fileInputRef = useRef(null);
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

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    setError("");
    setSuccess("");
    job.reset();

    // Checked here as well as on the server so an obviously wrong file costs nothing.
    if (file.type !== "application/pdf") {
      setError("Only PDF files are accepted.");
      e.target.value = "";
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`This file is ${(file.size / 1048576).toFixed(1)} MB, over the ${MAX_MB} MB limit.`);
      e.target.value = "";
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
      setSuccess(
        result.skipped
          ? `"${file.name}" was already indexed — ready straight away.`
          : `"${file.name}" is ready: ${result.pages} pages, ${result.chunks} chunks.`,
      );
      await refreshCount();
      onUploaded?.();
    }

    setSending(false);
    e.target.value = "";
  }

  const busy = sending || job.isRunning;

  return (
    <div className="bg-white rounded-lg shadow-sm p-5">
      <h2 className="font-medium mb-2">Documents</h2>
      <p className="text-sm text-gray-500 mb-3">
        {documentCount === null
          ? "Loading..."
          : documentCount === 0
            ? "No documents yet — upload one to get started."
            : `${documentCount} document${documentCount === 1 ? "" : "s"} uploaded.`}
      </p>

      {documentCount > 0 && (
        <a href="/documents" className="text-sm text-blue-600 hover:underline block mb-3">
          View all documents →
        </a>
      )}

      <label className="block text-sm font-medium mb-1" htmlFor="subject">
        Subject
      </label>
      <select
        id="subject"
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        disabled={busy}
        className="w-full mb-3 border rounded px-2 py-1.5 text-sm"
      >
        {SUBJECTS.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        disabled={busy}
        className="text-sm w-full"
      />

      {/* Phase 1: bytes going up. Only shown while it is actually happening -- once the
          server has the file, the interesting number is the job's. */}
      {sending && job.isRunning && progress < 100 && (
        <div className="mt-2 w-full bg-gray-200 rounded h-2">
          <div className="bg-blue-600 h-2 rounded transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}

      {/* Phase 2: what the backend is doing with it. */}
      <JobProgress job={job} className="mt-3" />

      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      {success && <p className="text-sm text-green-600 mt-2">{success}</p>}
    </div>
  );
}

export default DocumentsCard;
