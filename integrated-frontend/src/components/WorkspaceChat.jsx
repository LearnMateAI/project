/**
 * Chat bound to one document, for the split workspace.
 *
 * Same endpoints as the Chat page: create or reuse a session, POST a message, poll the
 * job. Kept here so a student can keep the PDF open while they ask, instead of leaving
 * /documents for /chat.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createSession, getMessages, listSessions, sendMessage } from "../api/chat.js";
import { errorMessage } from "../api/client.js";
import { useJob } from "../hooks/useJob.js";
import ChatMessage from "./ChatMessage.jsx";
import EmptyState from "./EmptyState.jsx";
import JobProgress from "./JobProgress.jsx";
import StreamingMessage from "./StreamingMessage.jsx";

function WorkspaceChat({ documentId, ready }) {
  const [sessionId, setSessionId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const job = useJob();
  const bottomRef = useRef(null);

  const openSession = useCallback(async () => {
    if (!documentId || !ready) {
      setSessionId(null);
      setTurns([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const listed = await listSessions();
      const existing = (listed.data || []).find((session) => session.document_id === documentId);
      if (existing) {
        setSessionId(existing.session_id);
        const messages = await getMessages(existing.session_id);
        setTurns(messages.data || []);
      } else {
        const created = await createSession({ documentId });
        setSessionId(created.data.session_id);
        setTurns([]);
      }
    } catch (err) {
      setError(errorMessage(err, "Could not open a conversation for this document."));
    } finally {
      setLoading(false);
    }
  }, [documentId, ready]);

  useEffect(() => {
    // Fetch-on-mount (and again if the selected document changes). The rule guards
    // against cascading renders from derived state; this is a request to an external
    // system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    openSession();
    job.reset();
    // job.reset is stable; including it would clear a running turn on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openSession]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, job.progress]);

  async function handleSend(e) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || !sessionId || job.isRunning) return;

    setError("");
    setDraft("");
    const pendingId = `pending-${Date.now()}`;
    setTurns((current) => [...current, { id: pendingId, role: "user", content: message }]);

    const result = await job.run(() => sendMessage({ sessionId, message }));
    if (!result) {
      setTurns((current) => current.filter((turn) => turn.id !== pendingId));
      setDraft(message);
      return;
    }

    setTurns((current) => [
      ...current,
      {
        id: `reply-${Date.now()}`,
        role: "assistant",
        content: result.reply,
        mode: result.mode,
        score: result.score,
        accepted: result.accepted,
        attempts: result.attempts,
        query: result.query,
        standalone_query: result.standalone_query,
        contexts: result.contexts,
        citations: result.citations,
        pages: (result.contexts || []).map((context) => context.page_number),
      },
    ]);
  }

  if (!ready) {
    return (
      <EmptyState
        className="m-auto"
        body="Chat opens once this document is Ready — answers would otherwise come from general knowledge."
      />
    );
  }

  return (
    <div className="flex flex-col h-full min-h-[28rem]">
      {error && <p className="notice notice-error mx-4 mt-3">{error}</p>}

      <div className="flex-1 space-y-3.5 overflow-y-auto px-4 py-4 bg-background">
        {loading ? (
          <p className="flex items-center gap-2.5 text-[13px] text-muted">
            <span className="spinner" />
            Opening conversation...
          </p>
        ) : turns.length === 0 ? (
          <EmptyState body="Ask a question. Answers cite page and paragraph from this source." />
        ) : (
          turns.map((turn) => <ChatMessage key={turn.id} turn={turn} />)
        )}
        {job.isRunning ? <StreamingMessage progress={job.progress} /> : <JobProgress job={job} />}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="flex gap-2 p-3 border-t border-border bg-surface">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about this source…"
          disabled={job.isRunning || !sessionId}
          className="input flex-1 rounded-full"
        />
        <button
          type="submit"
          disabled={job.isRunning || !draft.trim() || !sessionId}
          className="btn-primary rounded-full px-4 shrink-0"
        >
          {job.isRunning ? <span className="spinner spinner-light" /> : "Ask"}
        </button>
      </form>
    </div>
  );
}

export default WorkspaceChat;
