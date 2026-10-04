import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

/**
 * Registration is Keycloak-only too, for the same reason as login.jsx: there is no local
 * account creation path anymore, so a form here would create accounts nobody could use to
 * sign in. This sends the visitor straight to Keycloak's hosted registration form.
 */
function Register() {
  const { registerWithKeycloak, isAuthenticated, checking } = useAuth();

  useEffect(() => {
    if (!checking && !isAuthenticated) {
      registerWithKeycloak();
    }
  }, [checking, isAuthenticated, registerWithKeycloak]);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <p className="text-sm text-muted">Redirecting to sign up...</p>
    </div>
  );
}

export default Register;
