/**
 * The header strip above the content column.
 *
 * Left: where you are, and the button that brings the navigation back -- always under lg,
 * where the rail is a drawer, and above lg only once the rail has been collapsed. Right:
 * notifications and the signed-in user's own name with an avatar.
 */

import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";
import { useTheme } from "../hooks/useTheme.js";

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

function Topbar({ onOpenNav, navHidden = false }) {
  const { user } = useAuth();
  const { isDark, toggle } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const title = TITLES.find((entry) => entry.match.test(location.pathname))?.title || "LearnMateAI";

  const initials = (user?.name || "U")
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <header className="bg-surface border-b border-border px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        {/* Always shown below lg, where the rail is a drawer that starts closed. Above lg
            it appears only once the rail has been collapsed -- it is the only way back, so
            hiding it in that state would strand the user without navigation. */}
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Show navigation"
          title="Show navigation"
          className={`btn-icon ${navHidden ? "" : "lg:hidden"}`}
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
        {/* The icon shows the theme you would get by pressing it, not the one you are in.
            A sun while already light reads as a state indicator and invites a click that
            appears to do nothing; aria-pressed carries the actual state for screen
            readers, which is where a state belongs. */}
        <button
          type="button"
          onClick={toggle}
          className="btn-icon rounded-full"
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          title={isDark ? "Light mode" : "Dark mode"}
          aria-pressed={isDark}
        >
          {isDark ? (
            <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
            </svg>
          ) : (
            <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
            </svg>
          )}
        </button>

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
