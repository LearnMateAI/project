import { useState, useEffect, useRef } from "react";
import { uploadDocument, listDocuments } from "../../api/routes.jsx";

const SUBJECTS = [
  "Constitutional Law",
  "Law of Contract",
  "Criminal Law",
  "Law of Torts",
  "Property Law",
  "General",
];

function DocumentsCard() {
  const [documentCount, setDocumentCount] = useState(null);
  const [subject, setSubject] = useState("General");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    refreshCount();
  }, []);

  async function refreshCount() {
    try {
      const res = await listDocuments();
      setDocumentCount(res.data.length);
    } catch {
      setDocumentCount(null);
    }
  }

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    setError("");
    setSuccess("");

    // Client-side validation (UI-03) — reject non-PDFs before any network call.
    if (file.type !== "application/pdf") {
      setError("Only PDF files are accepted.");
      e.target.value = "";
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError("File exceeds the maximum size of 50 MB.");
      e.target.value = "";
      return;
    }

    setUploading(true);
    setProgress(0);
    try {
      await uploadDocument({
        file,
        subject,
        onUploadProgress: (event) => {
          setProgress(Math.round((event.loaded * 100) / event.total));
        },
      });
      setSuccess(`"${file.name}" uploaded successfully.`);
      await refreshCount();
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed. Please try again.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

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

      <select
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        className="w-full mb-3 border rounded px-2 py-1.5 text-sm"
      >
        {SUBJECTS.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        onChange={handleFileChange}
        disabled={uploading}
        className="text-sm"
      />

      {uploading && (
        <div className="mt-2 w-full bg-gray-200 rounded h-2">
          <div className="bg-blue-600 h-2 rounded transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}

      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      {success && <p className="text-sm text-green-600 mt-2">{success}</p>}
    </div>
  );
}

export default DocumentsCard;