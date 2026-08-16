/**
 * Study material: four types, two scopes.
 *
 * `generateResource` returns `202 {job_id}` -- the resource itself arrives as the job's
 * result, and is identical to what `getResource` returns afterwards.
 *
 * The vocabulary is shared with the UI through RESOURCE_TYPES below, so the panel, the
 * viewer and the index page all name a type the same way and the labels live in one file.
 */

import api from "./client.js";

/**
 * The four resource types the backend can generate.
 *
 * `countLabel` is what `count` means for that type -- questions, points, or roughly
 * sentences -- which is not the same thing and is worth saying on the form.
 * `pooled: false` marks summary, the one type that cannot be asked for at a rate per page:
 * a summary is one artefact and folds rather than pooling.
 */
export const RESOURCE_TYPES = [
  { type: "summary", label: "Summary", countLabel: "sentences", pooled: false },
  { type: "keypoints", label: "Key Points", countLabel: "points", pooled: true },
  { type: "mcq", label: "MCQs", countLabel: "questions", pooled: true },
  { type: "practice_qsn", label: "Practice Questions", countLabel: "questions", pooled: true },
];

/** The display name for a stored resource, which carries the engine's own type name. */
export function resourceLabel(type) {
  return RESOURCE_TYPES.find((entry) => entry.type === type)?.label || type;
}

/**
 * Queue one generation run.
 *
 * scope    "passage"  -- one extract, optionally the pages best matching `topic`. Seconds.
 *          "document" -- the whole PDF, read in groups and pooled. Minutes, and the only
 *                        way to get a set that is about the whole document rather than
 *                        about its opening pages.
 * count    a total. For a summary, roughly how many sentences.
 * perPage  document scope only, and mutually exclusive with count: a rate that reads every
 *          page, where a total samples across the document.
 * evaluate false skips the judge -- roughly half the time, and the result is unreviewed.
 */
export function generateResource({
  documentId,
  resourceType,
  scope = "passage",
  topic,
  pages,
  count,
  perPage,
  evaluate = true,
  threshold,
}) {
  return api.post("/api/resources/generate", {
    document_id: documentId,
    resource_type: resourceType,
    scope,
    // Omitted rather than sent as empty: the backend treats null as "not given", and an
    // empty topic string would be searched for.
    topic: topic?.trim() || null,
    pages: pages?.length ? pages : null,
    count: count ?? null,
    per_page: perPage ?? null,
    evaluate,
    threshold: threshold ?? null,
  });
}

export function listResources({ documentId, resourceType } = {}) {
  return api.get("/api/resources", {
    params: { document_id: documentId, resource_type: resourceType },
  });
}

/** One resource with its whole attempt trail. */
export function getResource(resourceId) {
  return api.get(`/api/resources/${resourceId}`);
}

export function deleteResource(resourceId) {
  return api.delete(`/api/resources/${resourceId}`);
}
