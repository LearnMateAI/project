import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalytics } from "../api/analytics.js";
import { useAuth } from "../context/useAuth.js";

// The routes a signed-out visitor is allowed to reach, so `go()` leaves them alone.
const PUBLIC_PATHS = new Set(["/", "/home", "/about", "/tour"]);

const Icon = ({ d }) => (
  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d={d} />
  </svg>
);

const ICONS = {
  upload: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5",
  chat: "M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155",
  book: "M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.331 0 4.472.89 6.042 2.346M12 6.042a8.967 8.967 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.346",
};

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

  return (
    <div className="animate-fade-in pub">
      {/* Hero: copy on the left, a floating product preview on the right */}
      <section className="hero-panel p-8 lg:p-14 mb-8">
        <div className="hero-split">
          <div>
            <p className="eyebrow mb-4">AI study companion</p>
            {isAuthenticated ? (
              <h1 className="display display-xl !text-white m-0">
                Welcome back{user?.name ? <>, <em>{user.name.split(" ")[0]}</em></> : ""}
              </h1>
            ) : (
              <h1 className="display display-xl !text-white m-0">
                Study smarter with <em>your own</em> course material
              </h1>
            )}
            <p className="lede mt-5 mb-7">
              Upload your notes and readings, then get cited answers, summaries and practice
              questions drawn only from what you gave it.
            </p>
            <div className="flex flex-wrap gap-3 mb-7">
              <Link to={go("/try")} className="btn-solid-light">
                {isAuthenticated ? "Get Started" : "Create a free account"} <span aria-hidden>→</span>
              </Link>
              <Link to="/tour" className="btn-ghost-light">Take a tour</Link>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="chip">PDF · DOCX · PPTX · TEX</span>
              <span className="chip">Cited answers</span>
              <span className="chip">Quality-checked</span>
            </div>
          </div>

          <div className="mock-stack hidden lg:block" aria-hidden="true">
            <div className="mock-card a">
              <p className="mock-label">You asked</p>
              What is the test for a valid contract?
            </div>
            <div className="mock-card b">
              <p className="mock-label">LearnMate answered</p>
              A contract needs offer, acceptance, consideration and intention to create legal
              relations. <span className="cite">p. 14</span> <span className="cite">p. 17</span>
            </div>
            <div className="mock-card c">
              <p className="mock-label">Key points · generated</p>
              <div className="mock-bar" style={{ width: "92%" }} />
              <div className="mock-bar" style={{ width: "74%" }} />
              <div className="mock-bar" style={{ width: "83%" }} />
            </div>
          </div>
        </div>
      </section>

      {/* Stats for members, proof points for visitors */}
      {stats ? (
        <div className="proof mb-14">
          <div><strong>{stats.documents ?? 0}</strong><span>Sources</span></div>
          <div><strong>{stats.resources?.total ?? 0}</strong><span>Materials</span></div>
          <div><strong>{stats.sessions ?? 0}</strong><span>Conversations</span></div>
          <div><strong>{stats.questions_asked ?? 0}</strong><span>Questions asked</span></div>
        </div>
      ) : (
        <div className="proof mb-14">
          <div><strong>4</strong><span>File formats supported</span></div>
          <div><strong>100%</strong><span>Answers cite their source</span></div>
          <div><strong>2-step</strong><span>Generate, then judge</span></div>
          <div><strong>Local</strong><span>Models run on your infrastructure</span></div>
        </div>
      )}

      {/* Features as a bento grid */}
      <section className="mb-16">
        <p className="eyebrow mb-2">What you can do</p>
        <h2 className="section-title mb-6">Read, ask, and revise in one place</h2>
        <div className="bento">
          <Link to={go("/documents")} className="card feature-card big p-8 block no-underline">
            <div className="w-12 h-12 rounded-xl bg-primary-light text-primary flex items-center justify-center mb-5">
              <Icon d={ICONS.upload} />
            </div>
            <h3 className="text-[26px] font-semibold text-heading mb-2">File &amp; read</h3>
            <p className="text-[15px] text-muted leading-relaxed max-w-lg">
              Organise PDFs, notes, slides, and other course material. Extracted text is indexed
              for study, so everything you upload becomes searchable.
            </p>
          </Link>
          <Link to={go("/chat")} className="card feature-card tile-dark small p-8 block no-underline">
            <div className="w-12 h-12 rounded-xl bg-white/15 text-white flex items-center justify-center mb-5">
              <Icon d={ICONS.chat} />
            </div>
            <h3 className="text-[22px] font-semibold mb-2">Ask a question</h3>
            <p className="text-[14px] leading-relaxed m-0">
              Every answer cites the page, slide, or section it came from.
            </p>
          </Link>
          <Link to={go("/resources")} className="card feature-card half p-8 block no-underline">
            <div className="w-12 h-12 rounded-xl bg-cyan-light text-cyan flex items-center justify-center mb-5">
              <Icon d={ICONS.book} />
            </div>
            <h3 className="text-[22px] font-semibold text-heading mb-2">Study materials</h3>
            <p className="text-[14px] text-muted leading-relaxed m-0">
              Generate summaries, key points, and practice questions from your documents.
            </p>
          </Link>
          <div className="card half p-8 bg-primary-soft">
            <p className="eyebrow mb-2">Trust built in</p>
            <h3 className="text-[22px] font-semibold text-heading mb-2">A second model checks the first</h3>
            <p className="text-[14px] text-muted leading-relaxed m-0">
              Low-scoring output is flagged, never hidden, so you always know how much to rely on it.
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="mb-16">
        <p className="eyebrow mb-2">Three steps</p>
        <h2 className="section-title mb-8">From file to flashcards in minutes</h2>
        <div className="steps-row">
          {[
            ["1", "Upload", "Drop in a PDF, Word, PowerPoint or LaTeX file."],
            ["2", "Generate", "Pick summaries, key points, MCQs or practice questions."],
            ["3", "Ask & revise", "Chat with the document and check every answer against its source."],
          ].map(([n, t, d]) => (
            <div key={n}>
              <div className="step-dot mb-4">{n}</div>
              <h3 className="text-[22px] font-semibold text-heading mb-1.5">{t}</h3>
              <p className="text-[14px] text-muted leading-relaxed m-0 max-w-xs">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Closing call to action. Signed in, there is nothing to sign up for. */}
      {!isAuthenticated && (
        <section className="cta-band">
          <h2 className="display">Ready to start?</h2>
          <p>
            Create an account, upload your first document, and get summaries, key points, practice
            questions and a chat that answers from your own material.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link to="/register" className="btn-solid-light">Create a free account</Link>
            <Link to="/tour" className="btn-ghost-light">Take a tour first</Link>
          </div>
        </section>
      )}
    </div>
  );
}

export default HomePage;
