/**
 * The one Keycloak instance this app uses.
 *
 * A single shared instance, not one per component -- for the same reason api/client.js
 * exports one axios instance: this object holds real, ongoing state (the current token,
 * refresh timers), and two separate instances would each think they were the only one.
 *
 * initKeycloak() wraps .init() in a cached promise rather than calling it directly.
 * React 19's StrictMode deliberately runs every effect twice in development to surface
 * exactly this kind of bug, and keycloak-js hard-errors on a second .init() call on the
 * same instance ("can only be initialized once"). Caching the promise means every caller
 * -- however many times an effect fires -- gets the same in-flight or resolved result,
 * and the real .init() call happens exactly once no matter what.
 */
import Keycloak from "keycloak-js";

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || "/auth",
  realm: import.meta.env.VITE_KEYCLOAK_REALM || "learnmate",
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "learnmate-frontend",
});

let initPromise = null;

export function resetKeycloakInit() {
  initPromise = null;
}

export function initKeycloak(options) {
  if (!initPromise) {
    initPromise = keycloak.init(options);
  }
  return initPromise;
}

export default keycloak;
