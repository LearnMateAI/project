import { useState } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";

/**
 * The frame every signed-in page renders into: a fixed rail, a fixed header, and one
 * scrolling content column. The page itself never scrolls, so the navigation is always
 * where the user left it.
 */
function Layout({ children }) {
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="app-shell">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar onOpenNav={() => setNavOpen(true)} />
        <main className="flex-1 overflow-y-auto bg-background px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
          {/* Keyed on the route so each navigation replays the entrance, rather than the
              first page fading in and every later one appearing instantly. */}
          <div key={location.pathname} className="animate-fade-in max-w-[1400px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export default Layout;
