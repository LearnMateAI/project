import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Attach the JWT (if one exists) to every outgoing request automatically.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function registerUser({ name, email, password }) {
  return api.post("/api/auth/register", { name, email, password });
}

export function loginUser({ email, password }) {
  return api.post("/api/auth/login", { email, password });
}

export default api;