import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalytics } from "../api/analytics.js";
import { listResources, resourceLabel } from "../api/resources.js";
import { useAuth } from "../context/useAuth.js";

function HomePage() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState([]);

  const refresh = useCallback(async () => {
    try {
      const res = await getAnalytics();
      setStats(res.data);
    } catch {
      setStats(null);
    }
    try {
      const res = await listResources();
      setRecent(res.data.slice(0, 4));
    } catch {
      setRecent([]);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  const features = [
    {
      title: "Upload & Learn",
      desc: "Upload your PDF documents and let AI process, chunk, and embed them for intelligent study material generation.",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      ),
      link: "/documents",
      color: "text-primary bg-primary-light",
    },
    {
      title: "AI Chat",
      desc: "Have intelligent conversations about your documents. Get answers grounded in your uploaded material with source citations.",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
        </svg>
      ),
      link: "/chat",
      color: "text-accent bg-accent-light",
    },
    {
      title: "Smart Resources",
      desc: "Generate summaries, key points, MCQs, and practice questions — all reviewed by a second AI model for quality assurance.",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.331 0 4.472.89 6.042 2.346M12 6.042a8.967 8.967 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.346" />
        </svg>
      ),
      link: "/resources",
      color: "text-cyan bg-cyan-light",
    },
  ];

  const quickActions = [
    { label: "Upload a Document", to: "/documents", desc: "Start by uploading a PDF" },
    { label: "Start a Chat", to: "/chat", desc: "Ask questions about your docs" },
    { label: "View Analytics", to: "/analytics", desc: "Track your study progress" },
    { label: "Take a Tour", to: "/tour", desc: "Learn how the platform works" },
  ];

  return (
    <div className="animate-fade-in">
      {/* Hero */}
      <div className="hero-panel p-8 lg:p-10 mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div>
            <h1 className="text-[30px] lg:text-[34px] leading-tight font-bold text-white tracking-tight m-0">
              Welcome to LearnMateAI{user?.name ? `, ${user.name.split(" ")[0]}` : ""}
            </h1>
            <p className="text-white/75 text-[15px] leading-relaxed max-w-xl mt-3 mb-0">
              Your AI-powered study companion. Upload documents, generate tailored study materials,
              and chat with your content — all backed by intelligent quality assurance.
            </p>
          </div>
          <Link
            to="/try"
            className="inline-flex items-center gap-2 shrink-0 bg-white text-primary font-semibold text-[13.5px] rounded-xl px-6 py-3 no-underline hover:bg-white/90 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            Get Started
          </Link>
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4 mb-6">
          <div className="stat-card">
            <p className="stat-label">Documents</p>
            <p className="stat-value">{stats.documents ?? 0}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Resources</p>
            <p className="stat-value">{stats.resources?.total ?? 0}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Conversations</p>
            <p className="stat-value">{stats.sessions ?? 0}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Questions Asked</p>
            <p className="stat-value">{stats.questions_asked ?? 0}</p>
          </div>
        </div>
      )}

      {/* Features */}
      <div className="grid gap-4 md:grid-cols-3 mb-6">
        {features.map((f) => (
          <Link key={f.title} to={f.link} className="card card-hover p-6 block no-underline">
            <div className={`w-10 h-10 rounded-lg ${f.color} flex items-center justify-center mb-4`}>
              {f.icon}
            </div>
            <h3 className="text-[15px] font-semibold text-heading mb-1.5">{f.title}</h3>
            <p className="text-[13px] text-muted leading-relaxed">{f.desc}</p>
          </Link>
        ))}
      </div>

      {/* Quick actions + recent resources */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-[15px] font-semibold text-heading mb-4">Quick Actions</h2>
          <div className="grid grid-cols-2 gap-3">
            {quickActions.map((a) => (
              <Link
                key={a.label}
                to={a.to}
                className="border border-border rounded-lg p-3 hover:border-primary hover:bg-primary-light/30 transition-colors no-underline block"
              >
                <p className="text-[13px] font-medium text-heading">{a.label}</p>
                <p className="text-[11px] text-muted mt-0.5">{a.desc}</p>
              </Link>
            ))}
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[15px] font-semibold text-heading">Recent Resources</h2>
            <Link to="/resources" className="text-[12px] text-primary font-medium hover:underline">
              View all →
            </Link>
          </div>
          {recent.length === 0 ? (
            <p className="text-[13px] text-muted">
              No resources yet. Upload a document and generate your first study material.
            </p>
          ) : (
            <ul className="space-y-2">
              {recent.map((r) => (
                <li key={r.id}>
                  <Link
                    to={`/resources/${r.id}`}
                    className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-background transition-colors no-underline"
                  >
                    <span className="text-[13px] font-medium text-heading">
                      {resourceLabel(r.resource_type)}
                    </span>
                    <span className="text-[11px] text-subtle">
                      {new Date(r.created_at).toLocaleDateString()}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export default HomePage;
