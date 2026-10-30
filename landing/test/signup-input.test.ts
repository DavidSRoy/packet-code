import { test } from "node:test";
import assert from "node:assert/strict";
import { parseQuery, parseSignup } from "../src/lib/signup-input.ts";

test("email is trimmed and lowercased", () =>
  assert.deepEqual(parseSignup({ email: "  Ana@Example.com " }), { ok: true, value: { email: "ana@example.com", q: null, utmSource: null, utmMedium: null, utmCampaign: null, referrer: null } }));
test("bad emails are rejected", () => { for (const e of ["", "ana", "a@b", "a".repeat(250) + "@x.co", 42, null]) assert.deepEqual(parseSignup({ email: e }), { ok: false, error: "invalid_email" }); });
test("strings are capped at 200 and unknown fields ignored", () => {
  const r = parseSignup({ email: "a@b.co", utm_source: "x".repeat(500), inArea: true });
  assert.ok(r.ok && r.value.utmSource?.length === 200 && !("inArea" in r.value));
});
test("blank optional strings become null", () => { const r = parseSignup({ email: "a@b.co", q: "   " }); assert.ok(r.ok && r.value.q === null); });
test("query must be 1 to 200 characters", () => {
  assert.deepEqual(parseQuery({ q: "  " }), { ok: false, error: "invalid_query" });
  assert.deepEqual(parseQuery({ q: "x".repeat(201) }), { ok: false, error: "invalid_query" });
  assert.deepEqual(parseQuery({ q: " NE 45th St " }), { ok: true, q: "NE 45th St" });
});
