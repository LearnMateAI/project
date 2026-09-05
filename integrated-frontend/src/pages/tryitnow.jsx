import { useState } from "react";
import { Link } from "react-router-dom";
import DocumentsCard from "../components/DocumentsCard.jsx";

function TryItNow() {
  const [currentStep, setCurrentStep] = useState(1);
  const [uploadedDoc, setUploadedDoc] = useState(null);

  function handleUploaded() {
    setUploadedDoc(true);
    setCurrentStep(2);
  }

  const steps = [
    { num: 1, label: "Upload" },
    { num: 2, label: "Generate" },
    { num: 3, label: "Review" },
  ];

  return (
    <div className="animate-fade-in max-w-3xl">
      <div className="page-header mb-6">
        <h1>Try It Now</h1>
        <p>File a PDF and generate an IRAC brief, flashcards, or bar-style MCQs</p>
      </div>

      {/* Step indicator */}
      <div className="card p-4 mb-6">
        <div className="flex items-center justify-center gap-0">
          {steps.map((step, i) => (
            <div key={step.num} className="flex items-center">
              <button
                onClick={() => setCurrentStep(step.num)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-colors ${
                  currentStep === step.num
                    ? "bg-primary text-white"
                    : currentStep > step.num
                      ? "bg-success-light text-success"
                      : "bg-background text-muted"
                }`}
              >
                {currentStep > step.num ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                ) : (
                  <span className="w-5 h-5 rounded-full border-2 flex items-center justify-center text-[11px] font-bold border-current">
                    {step.num}
                  </span>
                )}
                {step.label}
              </button>
              {i < steps.length - 1 && (
                <div className="w-12 h-px bg-border mx-1" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step 1: Upload */}
      {currentStep === 1 && (
        <div className="animate-fade-in">
          <div className="card p-6 mb-4">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-primary-light text-primary flex items-center justify-center shrink-0">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
              </div>
              <div>
                <h2 className="text-[15px] font-semibold text-heading">Step 1: Upload a Document</h2>
                <p className="text-[13px] text-muted mt-1">
                  Choose a subject and upload a PDF, Word, PowerPoint, or LaTeX file. The system will extract, chunk, and index the content automatically.
                </p>
              </div>
            </div>
          </div>
          <DocumentsCard onUploaded={handleUploaded} />
        </div>
      )}

      {/* Step 2: Generate */}
      {currentStep === 2 && (
        <div className="animate-fade-in">
          <div className="card p-6">
            <div className="flex items-start gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-accent-light text-accent flex items-center justify-center shrink-0">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
              </div>
              <div>
                <h2 className="text-[15px] font-semibold text-heading">Step 2: Generate Study Material</h2>
                <p className="text-[13px] text-muted mt-1">
                  {uploadedDoc
                    ? "Your document is ready! Head to the Documents page to generate summaries, key points, MCQs, or practice questions."
                    : "Upload a document first, then you'll be able to generate study material from it."}
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { type: "Summary", desc: "A concise overview of the content", icon: "📝" },
                { type: "Flashcards", desc: "Key points you can flip through", icon: "💡" },
                { type: "MCQs", desc: "Multiple choice test questions", icon: "✅" },
                { type: "Practice Questions", desc: "Open-ended study questions", icon: "📖" },
              ].map((item) => (
                <div key={item.type} className="border border-border rounded-lg p-3.5">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-base">{item.icon}</span>
                    <span className="text-[13px] font-medium text-heading">{item.type}</span>
                  </div>
                  <p className="text-[12px] text-muted">{item.desc}</p>
                </div>
              ))}
            </div>

            <div className="mt-5 flex gap-3">
              <Link to="/documents" className="btn-primary">
                Open Documents →
              </Link>
              <button onClick={() => setCurrentStep(3)} className="btn-secondary">
                Next Step
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Review */}
      {currentStep === 3 && (
        <div className="animate-fade-in">
          <div className="card p-6">
            <div className="flex items-start gap-3 mb-5">
              <div className="w-10 h-10 rounded-lg bg-success-light text-success flex items-center justify-center shrink-0">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-[15px] font-semibold text-heading">Step 3: Review & Study</h2>
                <p className="text-[13px] text-muted mt-1">
                  Browse your generated resources, take MCQ quizzes, chat with your documents, and track your progress through analytics.
                </p>
              </div>
            </div>

            <div className="space-y-3 mb-5">
              {[
                { to: "/resources", label: "View Resources", desc: "Browse all generated study material" },
                { to: "/chat", label: "Chat with Documents", desc: "Ask questions, get sourced answers" },
                { to: "/analytics", label: "Track Progress", desc: "View engagement and quality stats" },
              ].map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="flex items-center justify-between p-3 border border-border rounded-lg hover:border-primary hover:bg-primary-light/20 transition-colors no-underline"
                >
                  <div>
                    <p className="text-[13px] font-medium text-heading">{item.label}</p>
                    <p className="text-[11px] text-muted">{item.desc}</p>
                  </div>
                  <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </Link>
              ))}
            </div>

            <Link to="/dashboard" className="btn-primary">
              Go to Dashboard
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default TryItNow;
