import { useState } from "react";
import { Link } from "react-router-dom";

const tourSteps = [
  {
    num: 1,
    title: "Upload a Document",
    desc: "Head to the Dashboard and upload any PDF document. The system accepts lecture notes, textbooks, case law, or any study material up to 10 MB. Choose a subject category and the platform will take care of the rest.",
    detail: "The upload extracts text, splits it into chunks, and generates vector embeddings — building an intelligent index of your document's content.",
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
    desc: "Once your document is ready, open it from the Documents page and choose what to generate. You can create summaries, key points, MCQs, or practice questions — for a specific topic or the entire document.",
    detail: "Every generation is reviewed by an independent AI judge model. Results that score below the pass mark are flagged but still shown — nothing is hidden.",
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
    detail: "The chat shows which pages were used, the retrieval score, and even the raw text chunks — so you can always verify an answer against the source.",
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
    detail: "The analytics page also shows which evaluation stage decided each attempt — useful for understanding whether the generation prompt or the pass mark needs adjusting.",
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
  const [expandedStep, setExpandedStep] = useState(null);

  return (
    <div className="animate-fade-in max-w-3xl">
      <div className="page-header mb-8">
        <h1>Take a Tour</h1>
        <p>A step-by-step guide to getting the most out of LearnMateAI</p>
      </div>

      {/* Progress indicator */}
      <div className="flex items-center gap-0 mb-8 px-4">
        {tourSteps.map((step, i) => (
          <div key={step.num} className="flex items-center flex-1 last:flex-none">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-semibold shrink-0 ${
              expandedStep === i ? "bg-primary text-white" : "bg-primary-light text-primary"
            }`}>
              {step.num}
            </div>
            {i < tourSteps.length - 1 && (
              <div className="flex-1 h-px bg-border mx-2" />
            )}
          </div>
        ))}
      </div>

      {/* Steps */}
      <div className="space-y-4 mb-8">
        {tourSteps.map((step, i) => (
          <div
            key={step.num}
            className={`card overflow-hidden transition-all duration-200 ${
              expandedStep === i ? "ring-1 ring-primary/20" : ""
            }`}
          >
            <button
              onClick={() => setExpandedStep(expandedStep === i ? null : i)}
              className="w-full p-5 flex items-center gap-4 text-left hover:bg-background/50 transition-colors"
            >
              <div className={`w-12 h-12 rounded-xl ${step.color} flex items-center justify-center shrink-0`}>
                {step.icon}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[11px] font-bold text-primary">Step {step.num}</span>
                </div>
                <h3 className="text-[15px] font-semibold text-heading">{step.title}</h3>
                <p className="text-[13px] text-muted mt-1 leading-relaxed">{step.desc}</p>
              </div>
              <svg
                className={`w-5 h-5 text-muted shrink-0 transition-transform duration-200 ${
                  expandedStep === i ? "rotate-180" : ""
                }`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>

            {expandedStep === i && (
              <div className="px-5 pb-5 animate-fade-in">
                <div className="ml-16 pl-4 border-l-2 border-primary-light">
                  <p className="text-[13px] text-body leading-relaxed mb-3">{step.detail}</p>
                  <Link to={step.link} className="btn-primary text-[13px] py-1.5 px-4">
                    {step.linkLabel} →
                  </Link>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="card p-6 text-center">
        <h3 className="text-[15px] font-semibold text-heading mb-2">Ready to start learning?</h3>
        <p className="text-[13px] text-muted mb-4">Upload your first document and experience AI-powered study.</p>
        <Link to="/dashboard" className="btn-primary py-2.5 px-6">
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}

export default TakeATourPage;
