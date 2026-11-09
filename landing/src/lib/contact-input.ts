export const CONTACT_TOPICS = ["shop", "building", "press", "other"] as const;
export type ContactTopic = (typeof CONTACT_TOPICS)[number];

export interface ContactInput {
  topic: ContactTopic;
  name: string;
  email: string;
  org: string | null;
  message: string | null;
  utmSource: string | null;
  utmMedium: string | null;
  utmCampaign: string | null;
  referrer: string | null;
}

export type ContactError = "invalid_topic" | "invalid_name" | "invalid_email" | "invalid_message";

const MAX_EMAIL = 254;
const MAX_FIELD = 200;
export const MAX_MESSAGE = 2000;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isContactTopic(value: unknown): value is ContactTopic {
  return typeof value === "string" && (CONTACT_TOPICS as readonly string[]).includes(value);
}

function field(body: unknown, key: string): unknown {
  return typeof body === "object" && body !== null && key in body ? Reflect.get(body, key) : undefined;
}

function trimmed(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** Trimmed string capped at 200 characters; blank or non-string becomes null. */
function optionalString(value: unknown): string | null {
  const t = trimmed(value).slice(0, MAX_FIELD);
  return t === "" ? null : t;
}

export function parseContact(body: unknown): { ok: true; value: ContactInput } | { ok: false; error: ContactError } {
  const topic = field(body, "topic");
  if (!isContactTopic(topic)) return { ok: false, error: "invalid_topic" };

  const name = trimmed(field(body, "name"));
  if (name.length < 1 || name.length > MAX_FIELD) return { ok: false, error: "invalid_name" };

  const email = trimmed(field(body, "email")).toLowerCase();
  if (email.length > MAX_EMAIL || !EMAIL_PATTERN.test(email)) return { ok: false, error: "invalid_email" };

  const message = trimmed(field(body, "message"));
  if (message.length > MAX_MESSAGE) return { ok: false, error: "invalid_message" };

  return {
    ok: true,
    value: {
      topic,
      name,
      email,
      org: optionalString(field(body, "org")),
      message: message === "" ? null : message,
      utmSource: optionalString(field(body, "utm_source")),
      utmMedium: optionalString(field(body, "utm_medium")),
      utmCampaign: optionalString(field(body, "utm_campaign")),
      referrer: optionalString(field(body, "referrer")),
    },
  };
}

/** True when the hidden field that people never see was filled in, which only bots do. */
export function isHoneypotFilled(body: unknown): boolean {
  return trimmed(field(body, "website")) !== "";
}
