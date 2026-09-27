/**
 * The blue half of the sign-in and sign-up screens.
 *
 * Shared rather than duplicated so the two pages cannot drift apart, and hidden below lg,
 * where a full-height decorative panel would push the form off the first screen -- the one
 * thing a login page must not do.
 */

const points = [
  "Summaries, key points, MCQs and practice questions from your own documents",
  "Every answer in chat cites the pages it came from",
  "A second model grades each generation, and low scores are flagged, not hidden",
];

function AuthAside({ heading, blurb }) {
  return (
    <aside className="auth-aside hidden lg:flex flex-col justify-between p-12">
      <div className="relative z-10 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-white/15 backdrop-blur flex items-center justify-center">
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342" />
          </svg>
        </div>
        <span className="text-[17px] font-extrabold tracking-tight">LearnMateAI</span>
      </div>

      <div className="relative z-10 max-w-md">
        <h2 className="text-[34px] leading-[1.15] font-bold text-white tracking-tight m-0">
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
