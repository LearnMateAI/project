/**
 * The axios instance every other api/ module is built on.
 *
 * Two interceptors, and the second one matters more than it looks:
 *
 *   request   attach the stored token to everything
 *   response  on 401, clear the session and send the user to /login
 *
 * Without that second one an expired token produces a confusing error on whichever page
 * happened to make the next call -- "Could not load documents", "Generation failed" --
 * when the real answer is "log in again". AuthProvider refreshes the access token itself
 * well before its 5-minute lifetime is up, so this fires only once the refresh token (and
 * so the underlying Keycloak session) has actually expired.
 */

import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      // A hard redirect rather than a router navigate: interceptors live outside React,
      // so there is no navigate() in scope here, and wiping the whole tree is the right
      // outcome for a dead session anyway.
      if (window.location.pathname !== "/login") {
        window.location.replace("/login");
      }
    }
    return Promise.reject(error);
  },
);

/**
 * The message to show for a failed request.
 *
 * The backend writes its errors for people to read -- "This PDF is password-protected",
 * "Session 's1' was opened for chat, not resource generation" -- so `detail` is used
 * verbatim wherever it exists rather than replaced with something vaguer.
 */
export function errorMessage(error, fallback = "Something went wrong. Please try again.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI's 422 body is an array of per-field objects; show the first one's message.
  if (Array.isArray(detail) && detail.length) {
    return detail[0]?.msg || fallback;
  }
  if (error?.code === "ERR_NETWORK") {
    return "Cannot reach the server. Is the backend running?";
  }
  return fallback;
}

export default api;
