import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

const tourSteps = [
  {
    num: 1,
    title: "Upload a Document",
    desc: "Head to the Dashboard and upload a PDF, Word (.docx), PowerPoint (.pptx), or LaTeX (.tex) file. The system accepts notes, readings, slides, or any study material up to 10 MB.",
    detail: "The upload extracts text, splits it into chunks, and generates vector embeddings, building an intelligent index of your document's content.",
    link: "/dashboard",
    linkLabel: "Go to Dashboard",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
    ),
    color: "bg-primary-light text-primary",
  },
  {
    num: 2,
    title: "Generate Study Material",
    desc: "Once your document is ready, open it from the Documents page and choose what to generate. You can create summaries, key points, MCQs, or practice questions for a specific topic or the entire document.",
    detail: "Every generation is reviewed by an independent AI judge model. Results that score below the pass mark are flagged but still shown, nothing is hidden.",
    link: "/documents",
    linkLabel: "View Documents",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
      </svg>
    ),
    color: "bg-accent-light text-accent",
  },
  {
    num: 3,
    title: "Chat with Your Document",
    desc: "Start a conversation about any processed document. Ask questions and get answers drawn directly from the content. Answers that come from your document are clearly labelled, and those from general knowledge are marked separately.",
    detail: "The chat shows which pages were used, the retrieval score, and even the raw text chunks so you can always verify an answer against the source.",
    link: "/chat",
    linkLabel: "Open Chat",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
      </svg>
    ),
    color: "bg-cyan-light text-cyan",
  },
  {
    num: 4,
    title: "Track Your Progress",
    desc: "Visit Analytics to see your study engagement at a glance. Track how many documents you've uploaded, resources generated, questions asked, and how the evaluator has scored your content.",
    detail: "The analytics page also shows which evaluation stage decided each attempt which is useful for understanding whether the generation prompt or the pass mark needs adjusting.",
    link: "/analytics",
    linkLabel: "View Analytics",
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
    color: "bg-success-light text-success",
  },
];

function TakeATourPage() {
  const { isAuthenticated } = useAuth();
  const [active, setActive] = useState(0);
  const step = tourSteps[active];
  const last = active === tourSteps.length - 1;

  return (
    <div className="animate-fade-in pub">
      <section className="hero-panel p-8 lg:p-14 mb-10">
        <p className="eyebrow mb-3">Guided tour</p>
        <h1 className="display display-xl !text-white m-0 max-w-3xl">
          Four steps to <em>studying</em> smarter
        </h1>
        <p className="lede mt-5 mb-0">
          A quick walk through LearnMateAI, from first upload to tracking progress.
        </p>
      </section>

      <div className="tour-grid mb-14">
        {/* Step selector */}
        <div className="space-y-3">
          <div className="tour-progress mb-4" aria-hidden="true">
            <div style={{ width: `${((active + 1) / tourSteps.length) * 100}%` }} />
          </div>
          {tourSteps.map((t, i) => (
            <button
              key={t.num}
              type="button"
              onClick={() => setActive(i)}
              aria-current={active === i ? "step" : undefined}
              className={`tour-tab ${active === i ? "active" : ""}`}
            >
              <span className="tab-num">{t.num}</span>
              <span className="text-[15px] font-bold">{t.title}</span>
            </button>
          ))}
        </div>

        {/* Detail stage */}
        <div key={step.num} className="tour-stage animate-fade-in">
          <span className="ghost-num" aria-hidden="true">{step.num}</span>
          <div className={`w-14 h-14 rounded-2xl ${step.color} flex items-center justify-center mb-5`}>
            {step.icon}
          </div>
          <p className="eyebrow mb-2">Step {step.num} of {tourSteps.length}</p>
          <h2 className="section-title mb-3">{step.title}</h2>
          <p className="text-[16px] text-body leading-relaxed mb-5">{step.desc}</p>

          <div className="rounded-2xl bg-primary-soft border border-border p-5 mb-7">
            <p className="mock-label" style={{ color: "var(--color-primary)" }}>Good to know</p>
            <p className="text-[14.5px] text-body leading-relaxed m-0">{step.detail}</p>
          </div>

          {/* Every step points into the workspace, which a visitor cannot reach.
              Showing them the step and then sending them to a login form reads as
              a trap, so signed out they are offered the account instead. */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-secondary px-4 py-2"
                disabled={active === 0}
                onClick={() => setActive(active - 1)}
              >
                ← Back
              </button>
              {!last && (
                <button type="button" className="btn-secondary px-4 py-2" onClick={() => setActive(active + 1)}>
                  Next →
                </button>
              )}
            </div>
            <Link
              to={isAuthenticated ? step.link : "/register"}
              className="btn-primary text-[13px] py-2 px-5 no-underline"
            >
              {isAuthenticated ? `${step.linkLabel} →` : "Sign up to try this →"}
            </Link>
          </div>
        </div>
      </div>

      {/* CTA */}
      <section className="cta-band">
        <h2 className="display">Ready to start learning?</h2>
        <p>Upload your first document and experience AI-powered study.</p>
        {isAuthenticated ? (
          <Link to="/dashboard" className="btn-solid-light">Go to Dashboard</Link>
        ) : (
          <Link to="/register" className="btn-solid-light">Create a free account</Link>
        )}
      </section>
    </div>
  );
}

export default TakeATourPage;
