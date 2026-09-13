/**
 * Routes.
 *
 * Three kinds, and the middle one is the reason this file is not just a list:
 *
 *   open       /login and /register, no frame of their own
 *   explore    Home, About and Take a Tour -- readable *before* signing up, which is the
 *              point of having them. Same page component either way; only the frame
 *              changes, because a visitor needs a header offering to sign them up and a
 *              member needs the rail they navigate the app with.
 *   protected  everything that needs a session and a document to work on
 *
 * `/` is Home rather than a redirect to the dashboard. A first-time visitor landing on a
 * login page has been asked to commit before being told what to.
 *
 * The resource routes are worth noting: there is one, `/resources/:resourceId`, which
 * fetches the resource and picks a renderer from its `resource_type`. The alternative --
 * a route per type, with the resource handed over in router state -- cannot survive a
 * refresh and cannot be linked to, which is a poor trade for something a student will want
 * to come back to.
 */

import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import PublicLayout from "./components/PublicLayout.jsx";
import { useAuth } from "./context/useAuth.js";

import AboutPage from "./pages/aboutpage.jsx";
import Analytics from "./pages/analytics.jsx";
import Chat from "./pages/chat.jsx";
import Dashboard from "./pages/dashboard.jsx";
import Documents from "./pages/documents.jsx";
import HomePage from "./pages/homepage.jsx";
import Login from "./pages/login.jsx";
import MyAccount from "./pages/myaccount.jsx";
import MyAccountSettings from "./pages/myaccountsettings.jsx";
import Register from "./pages/register.jsx";
import ResourceView from "./pages/resources/ResourceView.jsx";
import Resources from "./pages/resources/index.jsx";
import TakeATourPage from "./pages/takeatourpage.jsx";
import TryItNow from "./pages/tryitnow.jsx";

const protect = (element) => (
  <ProtectedRoute>
    <Layout>{element}</Layout>
  </ProtectedRoute>
);

/**
 * An Explore page, framed by whether there is a session.
 *
 * Signed in it belongs in the app and keeps the rail, exactly as it did when these routes
 * were protected; signed out it gets the public header instead of being bounced to /login.
 * `checking` is not waited on here: unlike ProtectedRoute there is no wrong redirect to
 * avoid, so the worst case is a visitor seeing the public frame for the moment it takes
 * Keycloak's check-sso to confirm a stored session, and a blank screen would be the worse
 * trade.
 */
function Explore({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Layout>{children}</Layout> : <PublicLayout>{children}</PublicLayout>;
}

const explore = (element) => <Explore>{element}</Explore>;

function App() {
  return (
    <Routes>
      <Route path="/" element={explore(<HomePage />)} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route path="/dashboard" element={protect(<Dashboard />)} />
      <Route path="/documents" element={protect(<Documents />)} />
      <Route path="/resources" element={protect(<Resources />)} />
      <Route path="/resources/:resourceId" element={protect(<ResourceView />)} />
      <Route path="/chat" element={protect(<Chat />)} />
      <Route path="/chat/:sessionId" element={protect(<Chat />)} />
      <Route path="/analytics" element={protect(<Analytics />)} />

      {/* Explore: readable without an account, and no longer listed in the signed-in rail
          -- a student who has already signed up does not need to be sold the product. They
          remain routable, so a link kept or shared still resolves, and a signed-in visitor
          gets them inside the app frame. /home is an alias for /. */}
      <Route path="/home" element={explore(<HomePage />)} />
      <Route path="/about" element={explore(<AboutPage />)} />
      <Route path="/tour" element={explore(<TakeATourPage />)} />

      <Route path="/account" element={protect(<MyAccount />)} />
      <Route path="/account/settings" element={protect(<MyAccountSettings />)} />
      {/* Not an Explore page: it works on a real document, so it needs a real session. */}
      <Route path="/try" element={protect(<TryItNow />)} />

      {/* Home, not the dashboard. An unknown URL from a signed-out visitor would otherwise
          land on /login with no explanation of what they had reached. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
