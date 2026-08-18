/**
 * Chat about one document.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createSession, deleteSession, getMessages, listSessions, sendMessage } from "../api/chat.js";
import { errorMessage } from "../api/client.js";
import { listDocuments } from "../api/documents.js";
import ChatMessage from "../components/ChatMessage.jsx";
import JobProgress from "../components/JobProgress.jsx";
import { useJob } from "../hooks/useJob.js";

function Chat() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [sessions, setSessions] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [loadingTurns, setLoadingTurns] = useState(false);
  const [starting, setStarting] = useState(false);

  const job = useJob();
  const bottomRef = useRef(null);

  const refreshSessions = useCallback(async () => {
    try {
      const res = await listSessions();
      setSessions(res.data);
      return res.data;
    } catch {
      setSessions([]);
      return [];
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshSessions();
    listDocuments()
      .then((res) => setDocuments(res.data.filter((doc) => doc.processing_status === "Ready")))
      .catch(() => setDocuments([]));
  }, [refreshSessions]);

  useEffect(() => {
    if (!sessionId) return undefined;

    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingTurns(true);
    getMessages(sessionId)
      .then((res) => {
        if (!cancelled) setTurns(res.data);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err, "Could not load this conversation."));
      })
      .finally(() => {
        if (!cancelled) setLoadingTurns(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, job.progress]);

  async function handleNewSession(documentId) {
    if (!documentId) return;
    setError("");
    setStarting(true);
    try {
      const res = await createSession({ documentId });
      await refreshSessions();
      navigate(`/chat/${res.data.session_id}`);
    } catch (err) {
      setError(errorMessage(err, "Could not start a conversation."));
    } finally {
      setStarting(false);
    }
  }

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
        top_score: result.top_score,
        score: result.score,
        accepted: result.accepted,
        attempts: result.attempts,
        query: result.query,
        standalone_query: result.standalone_query,
        contexts: result.contexts,
        pages: (result.contexts || []).map((context) => context.page_number),
      },
    ]);
    refreshSessions();
  }

  async function handleDeleteSession(session) {
    if (!window.confirm("Delete this conversation? The document is not affected.")) return;
    try {
      await deleteSession(session.session_id);
      const remaining = await refreshSessions();
      if (session.session_id === sessionId) {
        navigate(remaining.length ? `/chat/${remaining[0].session_id}` : "/chat");
      }
    } catch (err) {
      setError(errorMessage(err, "Could not delete this conversation."));
    }
  }

  const current = sessions.find((session) => session.session_id === sessionId);

  return (
    <div>
      <h1 className="font-display text-2xl font-bold mb-6 text-ink">Chat</h1>

      {error && <p className="text-sm text-danger mb-4">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <aside className="bg-white rounded-xl border border-gray-100 p-4 h-fit">
          <h2 className="font-medium text-sm mb-3 text-ink">New conversation</h2>
          {documents.length === 0 ? (
            <p className="text-sm text-muted mb-4">
              No documents are ready yet. Upload one and wait for it to finish processing.
            </p>
          ) : (
            <select
              value=""
              onChange={(e) => handleNewSession(e.target.value)}
              disabled={starting}
              className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm mb-4"
            >
              <option value="">Choose a document...</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
          )}

          <h2 className="font-medium text-sm mb-2 text-ink">Your conversations</h2>
          {sessions.length === 0 ? (
            <p className="text-sm text-muted">None yet.</p>
          ) : (
            <ul className="space-y-1">
              {sessions.map((session) => (
                <li key={session.session_id} className="flex items-center gap-1">
                  <button
                    onClick={() => navigate(`/chat/${session.session_id}`)}
                    className={`flex-1 text-left text-sm rounded-lg px-2 py-1.5 truncate ${
                      session.session_id === sessionId
                        ? "bg-ink-light text-ink"
                        : "text-muted hover:bg-gray-50"
                    }`}
                    title={session.filename}
                  >
                    {session.title || session.filename}
                  </button>
                  <button
                    onClick={() => handleDeleteSession(session)}
                    className="text-xs text-gray-300 hover:text-danger px-1"
                    title="Delete conversation"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="bg-white rounded-xl border border-gray-100 p-4 flex flex-col min-h-[32rem]">
          {!sessionId ? (
            <p className="text-sm text-muted m-auto">
              Pick a conversation, or start one from a document.
            </p>
          ) : (
            <>
              <div className="border-b border-gray-100 pb-2 mb-4">
                <p className="text-sm font-medium text-ink">{current?.filename || "Conversation"}</p>
                <p className="text-xs text-muted">
                  Answers are drawn from this document; anything it does not cover is answered
                  from general knowledge and labelled as such.
                </p>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto">
                {loadingTurns ? (
                  <p className="text-sm text-muted">Loading conversation...</p>
                ) : turns.length === 0 ? (
                  <p className="text-sm text-muted">
                    Ask a question about this document to get started.
                  </p>
                ) : (
                  turns.map((turn) => <ChatMessage key={turn.id} turn={turn} />)
                )}

                <JobProgress job={job} />
                <div ref={bottomRef} />
              </div>

              <form onSubmit={handleSend} className="mt-4 flex gap-2">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Ask a question about this document..."
                  disabled={job.isRunning}
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  disabled={job.isRunning || !draft.trim()}
                  className="bg-ink text-white rounded-lg px-4 py-2 text-sm hover:bg-ink/90 transition-colors disabled:opacity-50"
                >
                  {job.isRunning ? "Thinking..." : "Send"}
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

export default Chat;
