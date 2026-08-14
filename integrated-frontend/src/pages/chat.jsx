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
      <h1 className="text-2xl font-semibold mb-6">Chat</h1>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <aside className="bg-white rounded-lg shadow-sm p-4 h-fit">
          <h2 className="font-medium text-sm mb-3">New conversation</h2>
          {documents.length === 0 ? (
            <p className="text-sm text-gray-500 mb-4">
              No documents are ready yet. Upload one and wait for it to finish processing.
            </p>
          ) : (
            <select
              value=""
              onChange={(e) => handleNewSession(e.target.value)}
              disabled={starting}
              className="w-full border rounded px-2 py-1.5 text-sm mb-4"
            >
              <option value="">Choose a document...</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
          )}

          <h2 className="font-medium text-sm mb-2">Your conversations</h2>
          {sessions.length === 0 ? (
            <p className="text-sm text-gray-500">None yet.</p>
          ) : (
            <ul className="space-y-1">
              {sessions.map((session) => (
                <li key={session.session_id} className="flex items-center gap-1">
                  <button
                    onClick={() => navigate(`/chat/${session.session_id}`)}
                    className={`flex-1 text-left text-sm rounded px-2 py-1.5 truncate ${
                      session.session_id === sessionId
                        ? "bg-blue-100 text-blue-700"
                        : "text-gray-600 hover:bg-gray-100"
                    }`}
                    title={session.filename}
                  >
                    {session.title || session.filename}
                  </button>
                  <button
                    onClick={() => handleDeleteSession(session)}
                    className="text-xs text-gray-400 hover:text-red-600 px-1"
                    title="Delete conversation"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="bg-white rounded-lg shadow-sm p-4 flex flex-col min-h-[32rem]">
          {!sessionId ? (
            <p className="text-sm text-gray-400 m-auto">
              Pick a conversation, or start one from a document.
            </p>
          ) : (
            <>
              <div className="border-b pb-2 mb-4">
                <p className="text-sm font-medium">{current?.filename || "Conversation"}</p>
                <p className="text-xs text-gray-500">
                  Answers are drawn from this document; anything it does not cover is answered
                  from general knowledge and labelled as such.
                </p>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto">
                {loadingTurns ? (
                  <p className="text-sm text-gray-500">Loading conversation...</p>
                ) : turns.length === 0 ? (
                  <p className="text-sm text-gray-400">
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

              <form onSubmit={handleSend} className="mt-4 flex gap-2">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Ask a question about this document..."
                  disabled={job.isRunning}
                  className="flex-1 border rounded px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  disabled={job.isRunning || !draft.trim()}
                  className="bg-blue-600 text-white rounded px-4 py-2 text-sm disabled:opacity-50"
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
