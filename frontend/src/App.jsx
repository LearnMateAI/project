import { Routes, Route, Navigate } from "react-router-dom";
import Login from "../pages/login.jsx";
import Register from "../pages/register.jsx";
import Dashboard from "../pages/dashboard.jsx";
import ChatHome from "../pages/chat-home.jsx";
import Analytics from "../pages/user-analytics.jsx";
import ProtectedRoute from "./ProtectedRoute.jsx";
import Layout from "./components/Layout.jsx";
import Documents from "../pages/documents.jsx";
import ExplanationSummary from "../pages/resource-pages/explanation-summary.jsx";
import KeyPoints from "../pages/resource-pages/key-points.jsx";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
              <Layout>
            <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <Layout>
              <ChatHome />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/analytics"
        element={
          <ProtectedRoute>
            <Layout>
              <Analytics />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <Layout>
              <Documents />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/resources/summary"
        element={
          <ProtectedRoute>
            <Layout>
              <ExplanationSummary />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/resources/key-points"
        element={
          <ProtectedRoute>
            <Layout>
              <KeyPoints />
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;