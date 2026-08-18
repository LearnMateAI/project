import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/useAuth.js";

/**
 * Registration is Keycloak-only too, for the same reason as login.jsx: there is no local
 * account creation path anymore, so a form here would create accounts nobody could use to
 * sign in. Keycloak's own login page has its own "Register" link that reaches its
 * hosted registration form -- that is the real signup flow now.
 */
function Register() {
  const { loginWithKeycloak, isAuthenticated, checking } = useAuth();

  useEffect(() => {
    if (!checking && !isAuthenticated) {
      loginWithKeycloak();
    }
  }, [checking, isAuthenticated, loginWithKeycloak]);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper">
      <p className="text-sm text-muted">Redirecting to login...</p>
    </div>
  );
}

export default Register;
