/**
 * How a law student files a PDF: cases, statutes, course outlines, briefs.
 *
 * The backend has no matter-type field (documents are keyed by content hash and filed
 * under a subject). These labels live in localStorage so the library can be organised
 * without changing the API contract.
 */

export const MATTER_TYPES = [
  { id: "case", label: "Cases", singular: "Case" },
  { id: "statute", label: "Statutes", singular: "Statute" },
  { id: "outline", label: "Course Outlines", singular: "Course outline" },
  { id: "brief", label: "Briefs", singular: "Brief" },
];

const STORAGE_KEY = "learnmate-matter-types";

function readMap() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

export function getMatterType(documentId) {
  if (!documentId) return "";
  return readMap()[documentId] || "";
}

export function setMatterType(documentId, kind) {
  if (!documentId) return;
  const next = readMap();
  if (kind) next[documentId] = kind;
  else delete next[documentId];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function matterLabel(kind) {
  return MATTER_TYPES.find((entry) => entry.id === kind)?.singular || "Unfiled";
}
