/**
 * Chat: one conversation about one document.
 *
 * `sendMessage` returns `202 {job_id}`; the reply arrives as the job's result and carries
 * more than text -- which mode answered, what it scored, and the chunks it was written
 * from. The UI now shows only the last of those; the rest are still returned, and still
 * stored on the turn, for anyone reading the API or the database directly.
 *
 * The document must be Ready before a session can be opened against it. A session bound to
 * a PDF that is still being embedded would retrieve nothing and answer everything from
 * general knowledge, which reads as a broken assistant rather than an unfinished upload.
 */

import api from "./client.js";

export function createSession({ documentId, title }) {
  return api.post("/api/chat/sessions", { document_id: documentId, title });
}

export function listSessions() {
  return api.get("/api/chat/sessions");
}

/**
 * The transcript, oldest first.
 *
 * Assistant turns carry the same mode / score / pages metadata a live reply does, so a
 * conversation resumed tomorrow looks identical to one that never stopped.
 */
export function getMessages(sessionId) {
  return api.get(`/api/chat/sessions/${sessionId}/messages`);
}

export function sendMessage({ sessionId, message, evaluate = true, modelId }) {
  return api.post(`/api/chat/sessions/${sessionId}/messages`, {
    message,
    evaluate,
    model_id: modelId || null,
  });
}

export function deleteSession(sessionId) {
  return api.delete(`/api/chat/sessions/${sessionId}`);
}
