export interface SignupInput {
  email: string;
  q: string | null;
  utmSource: string | null;
  utmMedium: string | null;
  utmCampaign: string | null;
  referrer: string | null;
}

const MAX_EMAIL = 254;
const MAX_FIELD = 200;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function field(body: unknown, key: string): unknown {
  return typeof body === "object" && body !== null && key in body ? Reflect.get(body, key) : undefined;
}

/** Trimmed string capped at 200 characters; blank or non-string becomes null. */
function optionalString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim().slice(0, MAX_FIELD);
  return trimmed === "" ? null : trimmed;
}

export function parseQuery(body: unknown): { ok: true; q: string } | { ok: false; error: "invalid_query" } {
  const raw = field(body, "q");
  const q = typeof raw === "string" ? raw.trim() : "";
  if (q.length < 1 || q.length > MAX_FIELD) return { ok: false, error: "invalid_query" };
  return { ok: true, q };
}

export function parseSignup(body: unknown): { ok: true; value: SignupInput } | { ok: false; error: "invalid_email" } {
  const raw = field(body, "email");
  const email = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (email.length > MAX_EMAIL || !EMAIL_PATTERN.test(email)) return { ok: false, error: "invalid_email" };
  return {
    ok: true,
    value: {
      email,
      q: optionalString(field(body, "q")),
      utmSource: optionalString(field(body, "utm_source")),
      utmMedium: optionalString(field(body, "utm_medium")),
      utmCampaign: optionalString(field(body, "utm_campaign")),
      referrer: optionalString(field(body, "referrer")),
    },
  };
}
