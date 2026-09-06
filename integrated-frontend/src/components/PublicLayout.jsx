/**
 * The frame the Explore pages render into when nobody is signed in.
 *
 * Layout.jsx is the signed-in frame and cannot stand in for this one: its Topbar says
 * "Welcome back" beside an avatar and an account button, and its Sidebar links to
 * Documents, Chat and Analytics, every one of which bounces a visitor to /login. Showing
 * that to somebody who has not signed up yet advertises a wall rather than a product.
 *
 * So the same three pages get two frames, chosen by whether there is a session -- see the
 * `explore()` helper in App.jsx. The pages themselves are shared; only the chrome differs,
 * which is why this file holds no content of its own.
 */

import { Link, NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/about", label: "About" },
  { to: "/tour", label: "Take a Tour" },
];

function PublicLayout({ children }) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="bg-surface border-b border-border sticky top-0 z-30">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Same mark and wordmark as the signed-in rail, so the product does not appear
              to change identity at the moment somebody signs in. */}
          <Link to="/" className="flex items-center gap-3 no-underline shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-[0_6px_16px_-6px_rgba(35,64,224,0.55)]">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342" />
              </svg>
            </div>
            <span className="leading-none hidden sm:block">
              <span className="text-[16px] font-extrabold text-heading tracking-tight">LearnMate</span>
              <span className="text-[16px] font-extrabold text-primary tracking-tight">AI</span>
            </span>
          </Link>

          <nav className="flex items-center gap-1 sm:gap-2 min-w-0">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `px-2.5 sm:px-3.5 py-2 rounded-lg text-[13px] sm:text-[13.5px] font-semibold no-underline whitespace-nowrap transition-colors ${
                    isActive ? "text-primary bg-surface-alt" : "text-muted hover:text-heading"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2 shrink-0">
            <Link to="/login" className="btn-secondary text-[13px] py-2 px-3 sm:px-4 no-underline">
              Sign in
            </Link>
            {/* The one saturated element in the header, because it is the one thing this
                frame exists to lead to. */}
            <Link to="/register" className="btn-primary text-[13px] py-2 px-3 sm:px-4 no-underline hidden sm:inline-flex">
              Sign up
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1 px-4 py-6 sm:px-6 lg:py-8">
        <div className="max-w-[1200px] mx-auto">{children}</div>
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-5 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-[12px] text-subtle m-0">
            LearnMateAI — upload a document, ask it questions, generate study material from it.
          </p>
          <Link to="/register" className="text-[12.5px] font-semibold text-primary no-underline hover:underline">
            Create a free account
          </Link>
        </div>
      </footer>
    </div>
  );
}

export default PublicLayout;
