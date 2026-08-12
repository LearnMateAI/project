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
