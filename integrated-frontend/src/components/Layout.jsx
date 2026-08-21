import { useState } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";

/**
 * The frame every signed-in page renders into: a rail, a fixed header, and one scrolling
 * content column. The page itself never scrolls, so the navigation is always where the
 * user left it.
 *
 * Two independent pieces of navigation state, and they are separate on purpose:
 *
 *   navOpen    the mobile drawer. Slides the rail in over the content, and closes again
 *              on any navigation -- on a phone the rail covers what you just chose.
 *   collapsed  the desktop rail, hidden to give the content the full width. Navigating
 *              must *not* change it: a rail that vanished every time you clicked a link
 *              would be a bug, not a feature.
 *
 * One button drives each direction. The X in the rail hides it; the button in the header
 * brings it back, and that one is only visible when there is something to bring back.
 */
function Layout({ children }) {
  const [navOpen, setNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  // The X. Closes the drawer on a phone and collapses the rail on a desktop -- the same
  // gesture means "get this out of my way" on both, and only one of the two is visible at
  // any given width.
  function hideNav() {
    setNavOpen(false);
    setCollapsed(true);
  }

  // The header button, which is the only way back from either state.
  function showNav() {
    setNavOpen(true);
    setCollapsed(false);
  }

  return (
    <div className="app-shell">
      <Sidebar
        open={navOpen}
        collapsed={collapsed}
        onClose={() => setNavOpen(false)}
        onHide={hideNav}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Below lg the header button is always shown, because the rail is a drawer and
            always starts closed. Above lg it appears only once the rail is collapsed. */}
        <Topbar onOpenNav={showNav} navHidden={collapsed} />
        <main className="flex-1 overflow-y-auto bg-background px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
          {/* Keyed on the route so each navigation replays the entrance, rather than the
              first page fading in and every later one appearing instantly. */}
          <div key={location.pathname} className={`animate-fade-in mx-auto ${/^\/(documents|chat)/.test(location.pathname) ? "max-w-[1760px]" : "max-w-[1400px]"}`}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

export default Layout;
