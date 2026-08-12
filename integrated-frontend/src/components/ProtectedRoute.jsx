import { Navigate } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

function ProtectedRoute({ children }) {
  const { isAuthenticated, checking } = useAuth();

  // A stored token is verified against /api/auth/me on startup. Redirecting before that
  // answer arrives would bounce a perfectly valid session to the login page on every hard
  // refresh, so wait it out.
  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default ProtectedRoute;
