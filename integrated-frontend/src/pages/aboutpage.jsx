import { Link } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

const steps = [
  {
    num: "01",
    title: "Upload Your Document",
    desc: "Upload any PDF — lecture notes, textbooks, case law. The system extracts text, splits it into meaningful chunks, and builds a vector index for intelligent retrieval.",
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
    desc: "Choose what you need — summaries, key points, MCQs, or practice questions. A judge model reviews the output for quality, and flagged content is clearly marked.",
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

const techHighlights = [
  {
    title: "RAG Architecture",
    desc: "Retrieval-Augmented Generation ensures answers are grounded in your actual documents, not hallucinated.",
  },
  {
    title: "Quality Assurance",
    desc: "Every generated resource is independently reviewed by a judge model — pass rates and scores are transparently logged.",
  },
  {
    title: "Vector Search",
    desc: "Document chunks are embedded and stored in Qdrant, enabling semantic search that understands meaning beyond keywords.",
  },
  {
    title: "Local-First AI",
    desc: "Uses locally-hosted models for privacy and control. Your documents never leave your infrastructure.",
  },
];

function AboutPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="animate-fade-in max-w-4xl">
      {/* Header */}
      <div className="page-header mb-8">
        <h1>About LearnMateAI</h1>
        <p>An AI-powered study platform built for deeper learning</p>
      </div>

      {/* Mission */}
      <div className="card p-8 mb-6">
        <h2 className="text-lg font-semibold text-heading mb-3">Our Mission</h2>
        <p className="text-[14px] text-body leading-relaxed mb-3">
          LearnMateAI transforms how students engage with their study material. Instead of passively 
          reading through textbooks and lecture notes, students can upload their documents and let AI 
          generate tailored study resources — summaries, key points, multiple-choice questions, and 
          practice questions — all grounded in the actual content they need to learn.
        </p>
        <p className="text-[14px] text-body leading-relaxed">
          Originally designed for law students working with complex legal texts, the platform handles 
          any subject. Every piece of generated content is quality-checked by an independent AI judge, 
          and every answer in chat is traced back to its source pages — because study material you 
          cannot verify is study material you cannot trust.
        </p>
      </div>

      {/* How it works */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-heading mb-4">How It Works</h2>
        <div className="space-y-3">
          {steps.map((step) => (
            <div key={step.num} className="card p-5 flex gap-5 items-start">
              <div className="shrink-0 w-10 h-10 rounded-lg bg-primary-light text-primary flex items-center justify-center">
                {step.icon}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[11px] font-bold text-primary">{step.num}</span>
                  <h3 className="text-[14px] font-semibold text-heading">{step.title}</h3>
                </div>
                <p className="text-[13px] text-muted leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Technology */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-heading mb-4">Technology Highlights</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {techHighlights.map((t) => (
            <div key={t.title} className="card p-5">
              <h3 className="text-[14px] font-semibold text-heading mb-1.5">{t.title}</h3>
              <p className="text-[13px] text-muted leading-relaxed">{t.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="card p-6 text-center">
        <p className="text-[14px] text-muted mb-4">Ready to transform your study workflow?</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link to="/tour" className="btn-secondary no-underline">Take a Tour</Link>
          {/* Signed out, "Go to Dashboard" is a link to the login page wearing a
              misleading label. Offer the step that is actually available instead. */}
          {isAuthenticated ? (
            <Link to="/dashboard" className="btn-primary no-underline">Go to Dashboard</Link>
          ) : (
            <Link to="/register" className="btn-primary no-underline">Create a free account</Link>
          )}
        </div>
      </div>
    </div>
  );
}

export default AboutPage;
