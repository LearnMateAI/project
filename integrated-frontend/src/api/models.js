import api from "./client.js";

/** Generators this server can switch between. Omitted model_id still uses .env. */
export function listModels() {
  return api.get("/api/models");
}
