/**
 * Routes.
 *
 * Everything except /login and /register is behind ProtectedRoute and inside Layout, so
 * `protected(<Page />)` is written once rather than nesting two wrappers by hand on each
 * of the seven pages.
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

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route path="/dashboard" element={protect(<Dashboard />)} />
      <Route path="/documents" element={protect(<Documents />)} />
      <Route path="/resources" element={protect(<Resources />)} />
      <Route path="/resources/:resourceId" element={protect(<ResourceView />)} />
      <Route path="/chat" element={protect(<Chat />)} />
      <Route path="/chat/:sessionId" element={protect(<Chat />)} />
      <Route path="/analytics" element={protect(<Analytics />)} />

      <Route path="/home" element={protect(<HomePage />)} />
      <Route path="/about" element={protect(<AboutPage />)} />
      <Route path="/account" element={protect(<MyAccount />)} />
      <Route path="/account/settings" element={protect(<MyAccountSettings />)} />
      <Route path="/tour" element={protect(<TakeATourPage />)} />
      <Route path="/try" element={protect(<TryItNow />)} />

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
