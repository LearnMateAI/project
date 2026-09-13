/**
 * The app's top navigation: logo, primary nav as tabs, account.
 *
 * Replaces the icon rail (Sidebar.jsx) and the page-title bar (Topbar.jsx) with one
 * horizontal masthead, so the signed-in app is a single flat page rather than a framed
 * window beside a permanently-docked sidebar. Below lg the tabs collapse into a dropdown
 * panel triggered by the button next to the logo, rather than a drawer sliding over the
 * content -- there is no rail to slide, so a drawer would be solving a problem this layout
 * does not have.
 */

import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";
import { useTheme } from "../hooks/useTheme.js";

const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/documents", label: "Documents" },
  { to: "/chat", label: "Chat" },
  { to: "/resources", label: "Resources" },
  { to: "/analytics", label: "Analytics" },
];

function Masthead() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();

  const [accountOpen, setAccountOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const accountRef = useRef(null);

  // Close the account menu on an outside click -- the only way to dismiss it besides
  // choosing an item, since it has no backdrop of its own.
  useEffect(() => {
    if (!accountOpen) return undefined;
    function onPointerDown(e) {
      if (accountRef.current && !accountRef.current.contains(e.target)) setAccountOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [accountOpen]);

  function handleLogout() {
    setAccountOpen(false);
    // logout() already navigates the browser away itself -- it is a real page unload,
    // not a promise this can wait on -- so there is nothing left for this handler to do
    // once it returns. Calling navigate() afterward would race that unload: React Router
    // would mount a page in the same tick that Keycloak's redirect is about to replace
    // anyway, which is how "the logout button does nothing" bugs happen.
    logout();
  }

  const initials = (user?.name || "U")
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <header className="masthead relative">
      <div className="flex items-center gap-8 min-w-0">
        <Link to="/dashboard" className="masthead-logo no-underline shrink-0">
          LearnMate<em>AI</em>
        </Link>

        <nav className="hidden lg:flex items-center gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-tab ${isActive ? "is-active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <button
          type="button"
          onClick={() => setNavOpen((open) => !open)}
          aria-label="Toggle navigation"
          aria-expanded={navOpen}
          className="btn-icon lg:hidden"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
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

        <button type="button" className="btn-icon rounded-full" aria-label="Notifications">
          <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
          </svg>
        </button>

        <div className="relative" ref={accountRef}>
          <button
            type="button"
            onClick={() => setAccountOpen((open) => !open)}
            aria-expanded={accountOpen}
            className="flex items-center gap-2.5 pl-1 sm:pl-2 rounded-full hover:bg-surface-alt py-1 pr-1 transition-colors"
          >
            <span className="hidden sm:block text-[13px] font-semibold text-heading">
              {user?.name || "Account"}
            </span>
            <span className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-accent text-white flex items-center justify-center text-[12px] font-bold shrink-0">
              {initials}
            </span>
          </button>

          {accountOpen && (
            <div className="card absolute right-0 top-full mt-2 w-52 py-1.5 z-50 overflow-hidden animate-fade-in">
              <Link
                to="/account"
                onClick={() => setAccountOpen(false)}
                className="flex items-center gap-2.5 px-4 py-2.5 text-[13px] font-medium text-body no-underline hover:bg-surface-alt hover:text-heading"
              >
                My Account
              </Link>
              <Link
                to="/account/settings"
                onClick={() => setAccountOpen(false)}
                className="flex items-center gap-2.5 px-4 py-2.5 text-[13px] font-medium text-body no-underline hover:bg-surface-alt hover:text-heading"
              >
                Settings
              </Link>
              <div className="border-t border-border-light my-1" />
              <button
                type="button"
                onClick={handleLogout}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-[13px] font-medium text-danger hover:bg-danger-light"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </div>

      {navOpen && (
        <nav className="lg:hidden absolute top-full left-0 right-0 bg-surface border-b border-border shadow-lg z-40 p-3 flex flex-col gap-1 animate-fade-in">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) => `nav-tab ${isActive ? "is-active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}

export default Masthead;
