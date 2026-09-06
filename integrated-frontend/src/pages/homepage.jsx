import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalytics } from "../api/analytics.js";
import { useAuth } from "../context/useAuth.js";

// The routes a signed-out visitor is allowed to reach, so `go()` leaves them alone.
const PUBLIC_PATHS = new Set(["/", "/home", "/about", "/tour"]);

function HomePage() {
  const { user, isAuthenticated } = useAuth();
  const [stats, setStats] = useState(null);

  // Where a link should go for somebody who has not signed up yet. Most destinations on
  // this page need a session to do anything, so pointing a visitor at one would bounce
  // them to /login off the page that was meant to be selling them the idea -- send them
  // to sign up instead. The Explore pages are the exception: they are the reason a visitor
  // is allowed this far, so they are never redirected. See App.jsx.
  const go = (path) =>
    isAuthenticated || PUBLIC_PATHS.has(path) ? path : "/register";

  const refresh = useCallback(async () => {
    // Not merely pointless when signed out -- actively harmful. Both calls need a token,
    // and the 401 interceptor in api/client.js answers a rejection by wiping storage and
    // hard-redirecting to /login. Firing them here would throw a visitor off the public
    // home page a moment after it rendered. See api/client.js.
    if (!isAuthenticated) {
      setStats(null);
      return;
    }

    try {
      const res = await getAnalytics();
      setStats(res.data);
    } catch {
      setStats(null);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    // Fetch-on-mount. The rule guards against cascading renders from derived state;
    // this is a request to an external system, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  const features = [
    {
      title: "File & read",
      desc: "Organise PDFs, notes, slides, and other course material. Extracted text is indexed for study.",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      ),
      link: "/documents",
      color: "text-primary bg-primary-light",
    },
    {
      title: "Ask a Question",
      desc: "Keep the source open and ask beside it. Every answer cites the page, slide, or section it was retrieved from.",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
        </svg>
      ),
      link: "/chat",
      color: "text-accent bg-accent-light",
    },
    {
      title: "Study materials",
      desc: "Generate summaries, key points, and practice questions from your documents.",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.331 0 4.472.89 6.042 2.346M12 6.042a8.967 8.967 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.346" />
        </svg>
      ),
      link: "/resources",
      color: "text-cyan bg-cyan-light",
    },
  ];


  return (
    <div className="animate-fade-in">
      {/* Hero */}
      <div className="hero-panel p-8 lg:p-10 mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div>
            <h1 className="text-[30px] lg:text-[34px] leading-tight font-bold !text-white tracking-tight m-0">
              {isAuthenticated
                ? `Welcome to LearnMateAI${user?.name ? `, ${user.name.split(" ")[0]}` : ""}`
                : "Study smarter with your course material"}
            </h1>
            
          </div>
          <Link
            to={go("/try")}
            className="inline-flex items-center gap-2 shrink-0 bg-white text-primary font-semibold text-[13.5px] rounded-xl px-6 py-3 no-underline hover:bg-white/90 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            {isAuthenticated ? "Get Started" : "Create a free account"}
          </Link>
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4 mb-6">
          <div className="stat-card">
            <p className="stat-label">Sources</p>
            <p className="stat-value">{stats.documents ?? 0}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Materials</p>
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
          <Link key={f.title} to={go(f.link)} className="card card-hover p-6 block no-underline">
            <div className={`w-10 h-10 rounded-lg ${f.color} flex items-center justify-center mb-4`}>
              {f.icon}
            </div>
            <h3 className="text-[15px] font-semibold text-heading mb-1.5">{f.title}</h3>
            <p className="text-[13px] text-muted leading-relaxed">{f.desc}</p>
          </Link>
        ))}
      </div>

      {/* Quick actions + recent resources. Both describe a workspace, so signed out they
          are replaced by the one thing there is to do instead: sign up. */}
      {!isAuthenticated ? (
        <div className="card p-8 text-center">
          <h2 className="text-[19px] font-bold text-heading mb-2">Ready to start?</h2>
          <p className="text-[13.5px] text-muted leading-relaxed max-w-lg mx-auto mb-5">
            Create an account, upload your first document, and have summaries, key points, practice
            questions and a chat that answers from your own material.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link to="/register" className="btn-primary no-underline px-6 py-2.5">
              Create a free account
            </Link>
            <Link to="/tour" className="btn-secondary no-underline px-6 py-2.5">
              Take a tour first
            </Link>
          </div>
        </div>
      ) : (
      <div className="grid gap-6 lg:grid-cols-2">
        

        
      </div>
      )}
    </div>
  );
}

export default HomePage;
