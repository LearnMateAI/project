/**
 * Who is logged in.
 *
 * Keycloak-only: Login.jsx and Register.jsx both hand off to it immediately rather than
 * showing a form of their own, and nothing in this app talks to a local /api/auth/*
 * endpoint any more. So there is exactly one source of truth for a session -- the token
 * Keycloak issued -- and no `authProvider` flag is needed to tell it apart from another
 * kind, because another kind no longer exists.
 *
 * On mount, `checking` stays true until keycloak.init({ onLoad: "check-sso" }) resolves.
 * That call silently asks "is there already a session?" -- and, this is the part that
 * actually fixes Day 15's redirect problem, is also what parses a `?code=...` callback
 * after an explicit login. Previously nothing waited for that parsing to happen, so the
 * router's own "not logged in -> /login" redirect won the race against Keycloak's every
 * time. Holding `checking` true here is what ProtectedRoute trusts to avoid that race.
 */

import { useCallback, useEffect, useState } from "react";
import keycloak, { initKeycloak } from "../keycloak.js";
import { AuthContext } from "./AuthContext.js";

// Refresh with this much life left, comfortably inside the 5-minute access token
// lifetime, so a slow request never races an expiry mid-flight.
const REFRESH_MARGIN_SECONDS = 60;
const REFRESH_INTERVAL_MS = 20_000;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [checking, setChecking] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    // Deliberately NOT setToken(null)/setUser(null) here. Doing so used to re-render the
    // tree immediately -- a same-tick microtask -- and ProtectedRoute, still mounted on
    // whatever protected page logout was clicked from, saw isAuthenticated flip false and
    // rendered <Navigate to="/login" replace>. That is a client-side route change, not a
    // page load, so it wins every time against the *real* navigation keycloak.logout()
    // below is about to perform (the browser does not act on a pending navigation until
    // the current task finishes, and React's re-render happens well before that). Landing
    // on /login then fires Login.jsx's own auto-login effect, which overwrites the
    // pending logout redirect with a fresh one to Keycloak's *login* page before it ever
    // takes effect -- verified live, reproducible on every click. The token is already
    // gone from storage and the page is leaving for good either way, so there is nothing
    // for local render state to get right in the meantime.
    keycloak.logout({ redirectUri: window.location.origin + "/" });
  }, []);

  const loginWithKeycloak = useCallback(() => {
    keycloak.login({ redirectUri: window.location.origin + "/dashboard" });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function resolveSession() {
      try {
        const authenticated = await initKeycloak({
          onLoad: "check-sso",
          silentCheckSsoRedirectUri: window.location.origin + "/silent-check-sso.html",
          pkceMethod: "S256",
        });

        if (authenticated && !cancelled) {
          // The ID token Keycloak just issued already carries name/email as claims (the
          // "profile" and "email" scopes are on by default for this client) -- reading
          // them here is free. keycloak.loadUserProfile() used to be called instead, but
          // it is a *second*, separate REST call to Keycloak's Account API, and that
          // endpoint failing (CORS, the account console being disabled, network hiccups)
          // threw before the token below was ever stored. The OIDC login had genuinely
          // succeeded at that point -- only this app's own record of it was lost -- so
          // the user bounced straight back to /login, which auto-retries login, forever.
          const claims = keycloak.tokenParsed || {};
          const nextUser = {
            id: keycloak.subject,
            name: claims.name || claims.preferred_username || claims.email || "User",
            email: claims.email,
          };
          localStorage.setItem("token", keycloak.token);
          localStorage.setItem("user", JSON.stringify(nextUser));
          setToken(keycloak.token);
          setUser(nextUser);
        }
      } catch {
        // Keycloak unreachable, or genuinely no session -- either way this just means
        // "not logged in," not an error worth surfacing.
      }

      if (!cancelled) setChecking(false);
    }

    resolveSession();
    return () => {
      cancelled = true;
    };
    // Deliberately runs once, on mount only: re-running on every `token` change would
    // re-trigger check-sso right after this effect already set one directly.
  }, []);

  // Keep the token fresh so client.js's interceptor always attaches one with life left
  // in it -- Keycloak's access tokens last 5 minutes, which would otherwise expire
  // mid-session on essentially every page.
  useEffect(() => {
    if (!token) return undefined;

    const interval = setInterval(() => {
      keycloak
        .updateToken(REFRESH_MARGIN_SECONDS)
        .then((refreshed) => {
          if (refreshed) {
            localStorage.setItem("token", keycloak.token);
            setToken(keycloak.token);
          }
        })
        .catch(() => {
          // The refresh token itself expired. Same handling as any other dead session:
          // client.js's interceptor catches the next 401 and redirects.
        });
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [token]);

  const value = {
    user,
    token,
    logout,
    loginWithKeycloak,
    checking,
    isAuthenticated: !!token,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
