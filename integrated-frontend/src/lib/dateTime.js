const SRI_LANKA_TIME_ZONE = "Asia/Colombo";

export function formatSriLankaDateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: SRI_LANKA_TIME_ZONE,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "shortOffset",
  }).format(new Date(value));
}

/** "just now", "12 min ago", "3 h ago", "2 days ago" for an age in seconds. */
export function formatRelativeAge(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "";
  const s = Math.max(0, Number(seconds));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  const days = Math.round(s / 86400);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}
