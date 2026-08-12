/**
 * Who is logged in.
 *
 * The token and user are mirrored into localStorage so a refresh does not log you out, and
 * read back from it on first render so there is no flash of the login page.
 *
 * One addition over a plain store: a stored token is *verified* on mount against
 * GET /api/auth/me. Tokens expire after 24 hours, and without this the first sign of a
 * dead session is whichever call the user happens to make next failing for reasons that
 * look nothing like "log in again". `checking` is true until that answer comes back, so
 * ProtectedRoute can wait rather than bouncing a valid session to /login.
 */

import { useCallback, useEffect, useState } from "react";
import { getMe } from "../api/auth.js";
import { AuthContext } from "./AuthContext.js";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [checking, setChecking] = useState(() => !!localStorage.getItem("token"));

  const login = useCallback((newToken, newUser) => {
    localStorage.setItem("token", newToken);
    localStorage.setItem("user", JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
    setChecking(false);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    // `checking` is already false when there is no token -- see its initialiser -- so
    // there is nothing to wait for and nothing to set.
    if (!token) return undefined;

    let cancelled = false;
    getMe()
      .then(() => {
        if (!cancelled) setChecking(false);
      })
      .catch(() => {
        // A 401 has already been handled by the interceptor in api/client.js, which wipes
        // storage and redirects. Anything else -- the backend being down, say -- must not
        // log a user out: their token is probably fine and the server will come back.
        if (!cancelled) setChecking(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const value = { user, token, login, logout, checking, isAuthenticated: !!token };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
