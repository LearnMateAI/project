import { useLocation } from "react-router-dom";
import Masthead from "./Masthead.jsx";

/**
 * The frame every signed-in page renders into: the masthead, then one scrolling content
 * column beneath it -- a flat page rather than a rail-and-window shell, which was most of
 * what made the app read as a generic admin template.
 */
function Layout({ children }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background">
      <Masthead />
      <main className="px-4 py-7 sm:px-6 lg:px-8">
        {/* Keyed on the route so each navigation replays the entrance, rather than the
            first page fading in and every later one appearing instantly. */}
        <div key={location.pathname} className="animate-fade-in max-w-[1400px] mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}

export default Layout;
