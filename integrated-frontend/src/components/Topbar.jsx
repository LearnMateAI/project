/**
 * The header strip above the content column.
 *
 * Left: where you are (and, under lg, the button that opens the rail). Right: the three
 * things a signed-in user expects in that corner -- search, notifications, and their own
 * name with an avatar.
 *
 * Search jumps to whichever section owns the term rather than pretending to be a global
 * index: there is no search endpoint, and a box that silently does nothing is worse than
 * one that routes you to the page holding the thing you typed.
 */

import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

const TITLES = [
  { match: /^\/dashboard/, title: "Dashboard" },
  { match: /^\/documents/, title: "Documents" },
  { match: /^\/resources/, title: "Resources" },
  { match: /^\/chat/, title: "Chat" },
  { match: /^\/analytics/, title: "Analytics" },
  { match: /^\/home/, title: "Home" },
  { match: /^\/about/, title: "About" },
  { match: /^\/account\/settings/, title: "Settings" },
  { match: /^\/account/, title: "My Account" },
  { match: /^\/tour/, title: "Take a Tour" },
  { match: /^\/try/, title: "Try It Now" },
];

function Topbar({ onOpenNav }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [query, setQuery] = useState("");

  const title = TITLES.find((entry) => entry.match.test(location.pathname))?.title || "LearnMateAI";

  const initials = (user?.name || "U")
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  function handleSearch(e) {
    e.preventDefault();
    const term = query.trim().toLowerCase();
    if (!term) return;
    const destination =
      /chat|question|ask|conversation/.test(term) ? "/chat"
      : /mcq|quiz|summary|key ?point|practice|resource/.test(term) ? "/resources"
      : /score|analytic|stat|progress/.test(term) ? "/analytics"
      : "/documents";
    setQuery("");
    navigate(destination);
  }

  return (
    <header className="bg-surface border-b border-border px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          className="lg:hidden btn-icon"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>

        <div className="min-w-0">
          <h1 className="text-[15px] font-bold text-heading truncate leading-tight">{title}</h1>
          <p className="text-[11.5px] text-muted truncate leading-tight">
            Welcome back, {user?.name?.split(" ")[0] || "there"}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <form onSubmit={handleSearch} className="hidden md:block relative">
          <svg
            className="w-4 h-4 text-subtle absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your workspace..."
            aria-label="Search"
            className="input pl-9 w-56 lg:w-72 bg-surface-alt border-transparent rounded-full"
          />
        </form>

        <button type="button" className="btn-icon rounded-full relative" aria-label="Notifications">
          <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
          </svg>
        </button>

        <button
          type="button"
          onClick={() => navigate("/account")}
          className="flex items-center gap-2.5 pl-1 sm:pl-2 rounded-full hover:bg-surface-alt py-1 pr-1 transition-colors"
          title="My account"
        >
          <span className="hidden sm:block text-right leading-tight">
            <span className="block text-[13px] font-semibold text-heading">
              {user?.name || "Account"}
            </span>
            <span className="block text-[11px] text-muted">Student</span>
          </span>
          <span className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-accent text-white flex items-center justify-center text-[12px] font-bold shrink-0">
            {initials}
          </span>
        </button>
      </div>
    </header>
  );
}

export default Topbar;
