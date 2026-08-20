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
          {/* Same wordmark as the signed-in masthead, so the product does not appear to
              change identity at the moment somebody signs in. */}
          <Link to="/" className="masthead-logo no-underline shrink-0">
            LearnMate<em>AI</em>
          </Link>

          <nav className="flex items-center gap-1 sm:gap-2 min-w-0">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-tab ${isActive ? "is-active" : ""}`}
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
            LearnMateAI — upload a PDF, ask it questions, generate study material from it.
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
