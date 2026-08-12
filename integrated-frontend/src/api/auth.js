/**
 * Accounts.
 *
 * `register` and `login` both return {token, user}; `me` is what a stored token is checked
 * against on startup, so a session that expired overnight is caught before the user
 * clicks anything rather than on whichever call they happen to make first.
 */

import api from "./client.js";

export function registerUser({ name, email, password }) {
  return api.post("/api/auth/register", { name, email, password });
}

export function loginUser({ email, password }) {
  return api.post("/api/auth/login", { email, password });
}

export function getMe() {
  return api.get("/api/auth/me");
}
