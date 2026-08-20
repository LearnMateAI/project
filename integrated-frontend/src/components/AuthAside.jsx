/**
 * The blue half of the sign-in and sign-up screens.
 *
 * Shared rather than duplicated so the two pages cannot drift apart, and hidden below lg,
 * where a full-height decorative panel would push the form off the first screen -- the one
 * thing a login page must not do.
 */

const points = [
  "Summaries, key points, MCQs and practice questions from your own PDFs",
  "Every answer in chat cites the pages it came from",
  "A second model grades each generation, and low scores are flagged, not hidden",
];

function AuthAside({ heading, blurb }) {
  return (
    <aside className="auth-aside hidden lg:flex flex-col justify-between p-12">
      <div className="relative z-10 flex items-baseline gap-0.5 font-serif text-[19px] font-semibold text-white">
        LearnMate<em className="italic text-white/70">AI</em>
      </div>

      {/* A stacked-notebook illustration built from shapes, echoing the document stack on
          the marketing hero rather than a literal photo or a generic lock/shield icon. */}
      <div className="relative z-10 max-w-md">
        <div className="relative h-[190px] mb-9">
          <div className="absolute left-3 top-6 w-[150px] h-[170px] bg-white/10 border border-white/20 rounded-xl rotate-[-6deg]" />
          <div className="absolute left-16 top-0 w-[150px] h-[170px] bg-white rounded-xl shadow-2xl rotate-[4deg] p-5">
            <div className="w-3/5 h-2 bg-primary-light rounded-full mb-3" />
            <div className="w-[85%] h-1.5 bg-border-light rounded-full mb-1.5" />
            <div className="w-[75%] h-1.5 bg-border-light rounded-full mb-1.5" />
            <div className="w-[80%] h-1.5 bg-border-light rounded-full mb-4" />
            <div className="w-9 h-9 rounded-lg bg-primary-light flex items-center justify-center">
              <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
          </div>
        </div>
        <h2 className="font-serif italic text-[28px] leading-[1.3] font-medium text-white m-0">
          {heading}
        </h2>
        <p className="text-[14.5px] leading-relaxed text-white/75 mt-4 mb-8">{blurb}</p>

        <ul className="space-y-3.5 list-none p-0 m-0">
          {points.map((point) => (
            <li key={point} className="flex gap-3 text-[13.5px] text-white/85 leading-relaxed">
              <span className="shrink-0 w-5 h-5 rounded-full bg-white/15 flex items-center justify-center mt-0.5">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </span>
              {point}
            </li>
          ))}
        </ul>
      </div>

      <p className="relative z-10 text-[12px] text-white/50 m-0">© 2026 LearnMateAI</p>
    </aside>
  );
}

export default AuthAside;
