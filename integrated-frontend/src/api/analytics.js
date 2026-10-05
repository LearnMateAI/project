/**
 * Analytics.
 *
 * One call, because the page is one screen: activity counts, resources by type, and the
 * evaluation score distribution. That last half is only possible because the backend
 * grades its own output with a separate judge model and logs every verdict -- passes as
 * well as failures -- so the numbers are measured rather than estimated.
 */

import api from "./client.js";

export function getAnalytics() {
  return api.get("/api/analytics");
}

/**
 * Where the class gets stuck in one document: per-page confusion and question topics,
 * mined from every student's questions about the same (shared) document. Aggregate-only:
 * pages and topics with too few students come back suppressed.
 */
export function getDocumentHeatmap(documentId, { refresh = false } = {}) {
  return api.get(`/api/analytics/documents/${documentId}/heatmap`, {
    params: refresh ? { refresh: true } : undefined,
  });
}
