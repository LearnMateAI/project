/**
 * Documents.
 *
 * `uploadDocument` is the one that changed shape: it returns `{document, job_id}` with a
 * 202, not a finished document. The row it hands back exists immediately and appears in
 * the list as "Processing"; the job is what turns it into "Ready".
 *
 * `onUploadProgress` still works and still means what it did -- bytes going up the wire --
 * but that is now the fast part. The minutes are in the job that follows it.
 */

import api from "./client.js";

export function uploadDocument({ file, subject, onUploadProgress }) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("subject", subject);

  return api.post("/api/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress,
  });
}

export function listDocuments() {
  return api.get("/api/documents");
}

export function getDocument(documentId) {
  return api.get(`/api/documents/${documentId}`);
}

export function getDocumentFile(documentId) {
  return api.get(`/api/documents/${documentId}/file`, { responseType: "blob" });
}

/**
 * The cleaned page text -- running heads stripped, ligatures repaired, hyphenation joined.
 * Not the raw PDF text: this is what the models actually read, which makes it the honest
 * answer to "what did it see on page 41?".
 */
export function getDocumentPages(documentId, { first, last } = {}) {
  return api.get(`/api/documents/${documentId}/pages`, { params: { first, last } });
}

/**
 * Remove a document from this user's library.
 *
 * Returns {removed, purged}. `purged: false` means somebody else uploaded the same file,
 * so the bytes and vectors stay -- one PDF is stored once however many people have it.
 */
export function deleteDocument(documentId) {
  return api.delete(`/api/documents/${documentId}`);
}
