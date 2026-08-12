/**
 * Who is logged in.
 *
 * Two ways to arrive at that answer, mirroring the backend's app/deps.py: a token this
 * app's own /api/auth/login issued, or one Keycloak issued. Whichever is active is stored
 * under the same "token" key, so api/client.js's interceptor -- which just reads that one
 * key -- never needs to know which kind it is. "authProvider" (local|keycloak) is the one
 * extra bit of state that does need to know, because logging out of a Keycloak session
 * means telling Keycloak too, not just forgetting a token.
 *
 * On mount, `checking` stays true until one of two checks resolves:
 *   - a stored local token, verified against GET /api/auth/me, as before
 *   - keycloak.init({ onLoad: "check-sso" }), which silently asks "is there already a
 *     session?" -- and, this is the part that actually fixes Day 15's redirect problem,
 *     is also what parses a `?code=...` callback after an explicit login. Previously
 *     nothing waited for that parsing to happen, so the router's own "not logged in ->
 *     /login" redirect won the race against Keycloak's every time. Holding `checking`
 *     true here is the same pattern ProtectedRoute already trusted for local-token
 *     verification, just extended to cover the second kind of session too.
 */

import { useCallback, useEffect, useState } from "react";
import { getMe } from "../api/auth.js";
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

  const login = useCallback((newToken, newUser, provider = "local") => {
    localStorage.setItem("token", newToken);
    localStorage.setItem("user", JSON.stringify(newUser));
    localStorage.setItem("authProvider", provider);
    setToken(newToken);
    setUser(newUser);
    setChecking(false);
  }, []);

  const logout = useCallback(() => {
    const provider = localStorage.getItem("authProvider");
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("authProvider");
    setToken(null);
    setUser(null);
    // A local session has nothing further to tell anyone. A Keycloak session still
    // exists on Keycloak's side too -- clearing only localStorage here would let
    // logging back in silently succeed via check-sso, with no login page shown at all.
    if (provider === "keycloak") {
      keycloak.logout({ redirectUri: window.location.origin + "/login" });
    }
  }, []);

  const loginWithKeycloak = useCallback(() => {
    keycloak.login({ redirectUri: window.location.origin + "/dashboard" });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function resolveSession() {
      const storedToken = localStorage.getItem("token");
      const storedProvider = localStorage.getItem("authProvider");

      // A stored local token takes priority when present: it needs no round trip to
      // Keycloak's iframe to answer, and it's the more common case today.
      if (storedToken && storedProvider !== "keycloak") {
        try {
          await getMe();
        } catch {
          // A 401 is already handled by client.js's interceptor. Anything else -- the
          // backend being down -- must not log a valid session out.
        }
        if (!cancelled) setChecking(false);
        return;
      }

      try {
        const authenticated = await initKeycloak({
          onLoad: "check-sso",
          silentCheckSsoRedirectUri: window.location.origin + "/silent-check-sso.html",
          pkceMethod: "S256",
        });

        if (authenticated && !cancelled) {
          const profile = await keycloak.loadUserProfile();
          const nextUser = {
            id: keycloak.subject,
            name: profile.firstName
              ? `${profile.firstName} ${profile.lastName || ""}`.trim()
              : profile.username,
            email: profile.email,
          };
          localStorage.setItem("token", keycloak.token);
          localStorage.setItem("user", JSON.stringify(nextUser));
          localStorage.setItem("authProvider", "keycloak");
          setToken(keycloak.token);
          setUser(nextUser);
        }
      } catch {
        // Keycloak unreachable, or genuinely no session -- either way this just means
        // "not logged in via Keycloak," not an error worth surfacing.
      }

      if (!cancelled) setChecking(false);
    }

    resolveSession();
    return () => {
      cancelled = true;
    };
    // Deliberately runs once, on mount only: re-running on every `token` change would
    // re-trigger check-sso right after login() already set one directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep a Keycloak-issued token fresh so client.js's interceptor always attaches one
  // with life left in it. Local tokens (24h) don't need this; Keycloak's (5min) would
  // otherwise expire mid-session on essentially every page.
  useEffect(() => {
    if (localStorage.getItem("authProvider") !== "keycloak") return undefined;

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
    login,
    logout,
    loginWithKeycloak,
    checking,
    isAuthenticated: !!token,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
