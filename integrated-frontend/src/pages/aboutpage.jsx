import { Link } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

const steps = [
  {
    num: "01",
    title: "Upload Your Document",
    desc: "Upload a PDF, Word, PowerPoint, or LaTeX file - notes, readings, slides, or other course material. The system extracts text, splits it into meaningful chunks, and builds a searchable index.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
    ),
  },
  {
    num: "02",
    title: "AI Processes & Embeds",
    desc: "The backend cleans and chunks your PDF, generates embeddings with a local model, and stores them in a vector database. This takes a few minutes for a full textbook.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25z" />
      </svg>
    ),
  },
  {
    num: "03",
    title: "Generate Study Material",
    desc: "Choose what you need - summaries, key points, MCQs, or practice questions. A judge model reviews the output for quality, and flagged content is clearly marked.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
      </svg>
    ),
  },
  {
    num: "04",
    title: "Study & Track Progress",
    desc: "Chat with your documents, review generated materials, and track your engagement through detailed analytics. Every piece of content is traceable to its source.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
];

function AboutPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="animate-fade-in pub">
      {/* Hero */}
      <section className="hero-panel p-8 lg:p-14 mb-14">
        <div className="hero-split">
          <div>
            <p className="eyebrow mb-3">About us</p>
            <h1 className="display display-xl !text-white m-0">
              Built for <em>deeper</em> learning
            </h1>
            <p className="lede mt-5 mb-0">
              An AI-powered study platform where every answer can be traced back to its source.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["4", "document formats"],
              ["4", "kinds of study material"],
              ["1", "source for every answer"],
              ["0", "documents leave your servers"],
            ].map(([n, l]) => (
              <div key={l} className="rounded-2xl bg-white/10 border border-white/15 p-5">
                <div className="display text-[2.4rem] font-semibold text-white leading-none">{n}</div>
                <div className="text-[12.5px] text-white/75 mt-2">{l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Mission: pull-quote beside the explanation */}
      <section className="grid gap-10 lg:grid-cols-[1fr_1.1fr] items-start mb-16">
        <div>
          <p className="eyebrow mb-3">Our mission</p>
          <p className="pull-quote m-0">
            Study material you cannot verify is study material you cannot trust.
          </p>
        </div>
        <div className="space-y-4">
          <p className="text-[16px] text-body leading-relaxed m-0">
            LearnMateAI transforms how students engage with their study material. Instead of
            passively reading through textbooks and lecture notes, students upload their documents
            and let AI generate tailored study resources: summaries, key points, multiple-choice
            questions, and practice questions, all grounded in the actual content they need to learn.
          </p>
          <p className="text-[16px] text-body leading-relaxed m-0">
            Built for students working with complex course material, the platform handles any
            subject. Every piece of generated content is quality-checked by an independent review
            step, and every answer in chat is traced back to its source pages.
          </p>
        </div>
      </section>

      {/* How it works: vertical timeline */}
      <section className="mb-16">
        <p className="eyebrow mb-2">The process</p>
        <h2 className="section-title mb-8">How it works</h2>
        <div className="timeline">
          {steps.map((step) => (
            <div key={step.num} className="timeline-item">
              <div className="step-dot">{step.num}</div>
              <div className="card feature-card p-6">
                <div className="flex items-center gap-3 mb-2">
                  <span className="w-9 h-9 rounded-lg bg-primary-light text-primary flex items-center justify-center shrink-0">
                    {step.icon}
                  </span>
                  <h3 className="text-[21px] font-semibold text-heading m-0">{step.title}</h3>
                </div>
                <p className="text-[14.5px] text-muted leading-relaxed m-0">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="cta-band">
        <h2 className="display">Ready to transform your study workflow?</h2>
        <p>Upload a document and see where every answer comes from.</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link to="/tour" className="btn-ghost-light">Take a Tour</Link>
          {/* Signed out, "Go to Dashboard" is a link to the login page wearing a
              misleading label. Offer the step that is actually available instead. */}
          {isAuthenticated ? (
            <Link to="/dashboard" className="btn-solid-light">Go to Dashboard</Link>
          ) : (
            <Link to="/register" className="btn-solid-light">Create a free account</Link>
          )}
        </div>
      </section>
    </div>
  );
}

export default AboutPage;
