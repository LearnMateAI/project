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
  { type: "keypoints", label: "Flashcards (key points)", countLabel: "cards", pooled: true },
  { type: "mcq", label: "MCQs", countLabel: "questions", pooled: true },
  { type: "practice_qsn", label: "Practice Questions", countLabel: "questions", pooled: true },
];

/**
 * Law-student shortcuts. Each preset still maps onto one of the four engine types.
 * IRAC is a structured summary with a retrieval topic; flashcards are keypoints;
 * bar-style MCQs are hard MCQs.
 */
export const STUDY_PRESETS = [
  {
    id: "irac",
    title: "IRAC Case Brief",
    hint: "Issue · Rule · Application · Conclusion from the holding",
    resourceType: "summary",
    summaryStyle: "structured",
    topic: "IRAC case brief: Issue, Rule, Application, Conclusion of the principal holding",
    count: 12,
    scope: "passage",
  },
  {
    id: "flashcards",
    title: "Create Flashcards",
    hint: "Key points as cards you can flip through",
    resourceType: "keypoints",
    count: 12,
  },
  {
    id: "mbe",
    title: "Bar-style (MBE) MCQs",
    hint: "Hard stems with near-miss distractors",
    resourceType: "mcq",
    difficulty: "hard",
    count: 8,
  },
];

/** The display name for a stored resource, which carries the engine's own type name. */
export function resourceLabel(type, params) {
  const topic = String(params?.topic || "").toLowerCase();
  if (type === "summary" && topic.includes("irac")) return "IRAC Case Brief";
  if (type === "keypoints") return "Flashcards";
  if (type === "mcq" && params?.difficulty === "hard") return "Bar-style (MBE) MCQs";
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
  summaryStyle,
  difficulty,
  modelId,
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
    summary_style: summaryStyle || null,
    difficulty: difficulty || null,
    model_id: modelId || null,
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

/** Download a stored resource as .docx or .pptx. Does not regenerate. */
export async function exportResource(resourceId, format = "docx") {
  const response = await api.get(`/api/resources/${resourceId}/export`, {
    params: { format },
    responseType: "blob",
  });
  const blob = new Blob([response.data], { type: response.headers["content-type"] });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const disposition = response.headers["content-disposition"] || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  link.href = url;
  link.download = match?.[1] || `resource.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
