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
