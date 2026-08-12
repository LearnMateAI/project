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

export function uploadDocument({ file, subject, onUploadProgress }) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("subject", subject);

  return api.post("/api/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress,
  });
}

export function listDocuments() {
  return api.get("/api/documents");
}

export function getDocumentFile(documentId) {
  return api.get(`/api/documents/${documentId}/file`, { responseType: "blob" });
}

export function generateResource({ documentId, resourceType }) {
  return api.post("/api/resources/generate", { document_id: documentId, resource_type: resourceType });
}

export function listResources(documentId) {
  return api.get("/api/resources", { params: { document_id: documentId } });
}

export default api;