/**
 * Chat about one document.
 *
 * Sessions on the left, transcript and composer on the right. A session is bound to
 * exactly one PDF, so "new chat" is really "pick a document" — and the document has to be
 * Ready, because a session bound to one still being embedded retrieves nothing and answers
 * everything from general knowledge, which reads as a broken assistant rather than an
 * unfinished upload.
 *
 * Sending is a job: POST returns 202, then useJob polls until the reply lands. That is
 * 30-60 seconds on the local models, so the pending turn streams the reply as the model
 * writes it — see StreamingMessage — with the backend's own commentary ("Generating
 * (attempt 1/2)...", "Evaluating...") underneath it. The total wait is unchanged; what
 * changes is that the first words appear in a couple of seconds rather than at the end.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createSession, deleteSession, getMessages, listSessions, sendMessage } from "../api/chat.js";
import { errorMessage } from "../api/client.js";
import { listDocuments } from "../api/documents.js";
import ChatMessage from "../components/ChatMessage.jsx";
import JobProgress from "../components/JobProgress.jsx";
import StreamingMessage from "../components/StreamingMessage.jsx";
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
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // these are requests to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshSessions();
    listDocuments()
      .then((res) => setDocuments(res.data.filter((doc) => doc.processing_status === "Ready")))
      .catch(() => setDocuments([]));
  }, [refreshSessions]);

  // Load the transcript whenever the session in the URL changes.
  useEffect(() => {
    // No session selected: the placeholder renders instead of the transcript, so there is
    // nothing to clear. Picking a different session refetches and replaces it.
    if (!sessionId) return undefined;

    let cancelled = false;
    // Loading the transcript for the session named in the URL -- an external fetch,
    // not derived state.
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

    // Shown straight away so the question is on screen during the minute it takes to
    // answer. The backend writes *both* halves only once the reply exists, so if this
    // fails the turn was never stored -- and the optimistic one is removed below rather
    // than left to vanish on the next reload.
    const pendingId = `pending-${Date.now()}`;
    setTurns((current) => [...current, { id: pendingId, role: "user", content: message }]);

    const result = await job.run(() => sendMessage({ sessionId, message }));

    if (!result) {
      setTurns((current) => current.filter((turn) => turn.id !== pendingId));
      setDraft(message); // give the question back so it can be sent again
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
      <div className="page-header">
        <h1>Chat</h1>
        <p>Ask questions about a document and get answers that cite their pages</p>
      </div>

      {error && <p className="notice notice-error mb-4">{error}</p>}

      <div className="grid gap-5 lg:grid-cols-[17rem_1fr] items-start">
        <aside className="card">
          <div className="card-head">
            <h2>Conversations</h2>
          </div>

          <div className="card-body">
            <label className="field-label" htmlFor="new-session">
              New conversation
            </label>
            {documents.length === 0 ? (
              <p className="text-[12.5px] text-muted leading-relaxed">
                No documents are ready yet. Upload one and wait for it to finish processing.
              </p>
            ) : (
              <select
                id="new-session"
                value=""
                onChange={(e) => handleNewSession(e.target.value)}
                disabled={starting}
                className="select"
              >
                <option value="">Choose a document...</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename}
                  </option>
                ))}
              </select>
            )}

            {sessions.length === 0 ? (
              <p className="text-[12.5px] text-muted mt-5">No conversations yet.</p>
            ) : (
              <ul className="mt-5 space-y-1 list-none p-0 m-0">
                {sessions.map((session) => (
                  <li key={session.session_id} className="flex items-center gap-1 group">
                    <button
                      onClick={() => navigate(`/chat/${session.session_id}`)}
                      className={`flex-1 min-w-0 text-left text-[13px] font-medium rounded-lg px-2.5 py-2 truncate transition-colors ${
                        session.session_id === sessionId
                          ? "bg-primary-light text-primary-dark"
                          : "text-muted hover:bg-surface-alt hover:text-heading"
                      }`}
                      title={session.filename}
                    >
                      {session.title || session.filename}
                    </button>
                    <button
                      onClick={() => handleDeleteSession(session)}
                      className="shrink-0 w-6 h-6 rounded-md text-subtle hover:bg-danger-light hover:text-danger opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                      title="Delete conversation"
                      aria-label="Delete conversation"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        <section className="card flex flex-col h-[calc(100vh-14rem)] min-h-[30rem] overflow-hidden">
          {!sessionId ? (
            <div className="m-auto text-center px-6 py-10">
              <span className="icon-tile icon-tile-soft w-12 h-12 mb-3">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                </svg>
              </span>
              <p className="text-[14px] font-semibold text-heading m-0">No conversation selected</p>
              <p className="text-[13px] text-muted mt-1 m-0">
                Pick one on the left, or start a new one from a document.
              </p>
            </div>
          ) : (
            <>
              <div className="card-head">
                <div className="min-w-0">
                  <h2 className="truncate">{current?.filename || "Conversation"}</h2>
                  
                </div>
              </div>

              <div className="flex-1 space-y-3.5 overflow-y-auto px-4 py-5 bg-background">
                {loadingTurns ? (
                  <p className="flex items-center gap-2.5 text-[13px] text-muted">
                    <span className="spinner" />
                    Loading conversation...
                  </p>
                ) : turns.length === 0 ? (
                  <p className="text-[13px] text-muted text-center py-6">
                    Ask a question about this document to get started.
                  </p>
                ) : (
                  turns.map((turn) => <ChatMessage key={turn.id} turn={turn} />)
                )}

                {/* While the turn is running its reply streams in here; JobProgress is
                    left to report a failure, which is the one state the streaming bubble
                    has nothing to say about. */}
                {job.isRunning ? <StreamingMessage progress={job.progress} /> : <JobProgress job={job} />}
                <div ref={bottomRef} />
              </div>

              <form onSubmit={handleSend} className="flex gap-2.5 p-3.5 border-t border-border bg-surface">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Ask a question about this document..."
                  disabled={job.isRunning}
                  className="input flex-1 rounded-full"
                />
                <button
                  type="submit"
                  disabled={job.isRunning || !draft.trim()}
                  className="btn-primary rounded-full px-5 shrink-0"
                >
                  {job.isRunning ? (
                    <>
                      <span className="spinner spinner-light" />
                      Thinking...
                    </>
                  ) : (
                    <>
                      Send
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                      </svg>
                    </>
                  )}
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
