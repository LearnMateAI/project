import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

/**
 * Login is Keycloak-only: this page's whole job is to trigger the redirect immediately
 * rather than show a form. It stays a route (not folded into App.jsx) so a direct visit
 * to /login, or being bounced here by ProtectedRoute, both land somewhere real.
 */
function Login() {
  const { loginWithKeycloak, isAuthenticated, checking } = useAuth();

  useEffect(() => {
    if (!checking && !isAuthenticated) {
      loginWithKeycloak();
    }
  }, [checking, isAuthenticated, loginWithKeycloak]);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <p className="text-sm text-muted">Redirecting to login...</p>
    </div>
  );
}

export default Login;
