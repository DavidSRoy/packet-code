import { test } from "node:test";
import assert from "node:assert/strict";
import { isContactTopic, MAX_MESSAGE, parseContact } from "../src/lib/contact-input.ts";
import { handleContact } from "../src/server/handlers.ts";
import type { SignupDb } from "../src/server/signups.ts";

const VALID = { topic: "shop", name: " Ana Ruiz ", email: " Ana@Shop.com ", org: "Ana's Tacos", message: "  Hi!  " };

function fakeDb(fails = false) {
  const sql: string[] = [];
  const bound: unknown[][] = [];
  const db: SignupDb = {
    prepare: (text) => {
      sql.push(text);
      return {
        bind: (...values) => ({
          run: () => {
            if (fails) return Promise.reject(new TypeError("boom"));
            bound.push(values);
            return Promise.resolve({});
          },
        }),
      };
    },
  };
  return { db, sql, bound };
}

test("contact input: trims, lowercases the email and keeps the topic", () =>
  assert.deepEqual(parseContact(VALID), {
    ok: true,
    value: {
      topic: "shop",
      name: "Ana Ruiz",
      email: "ana@shop.com",
      org: "Ana's Tacos",
      message: "Hi!",
      utmSource: null,
      utmMedium: null,
      utmCampaign: null,
      referrer: null,
    },
  }));

test("contact input: org and message are optional", () => {
  const r = parseContact({ ...VALID, org: " ", message: "" });
  assert.ok(r.ok && r.value.org === null && r.value.message === null);
});

test("contact input: rejects an unknown topic", () => {
  for (const topic of ["", "Shop", "sales", 1, undefined]) {
    assert.deepEqual(parseContact({ ...VALID, topic }), { ok: false, error: "invalid_topic" });
  }
});

test("contact input: name is required", () =>
  assert.deepEqual(parseContact({ ...VALID, name: "   " }), { ok: false, error: "invalid_name" }));

test("contact input: bad email is rejected", () =>
  assert.deepEqual(parseContact({ ...VALID, email: "ana@shop" }), { ok: false, error: "invalid_email" }));

test("contact input: message is capped", () => {
  assert.deepEqual(parseContact({ ...VALID, message: "x".repeat(MAX_MESSAGE + 1) }), { ok: false, error: "invalid_message" });
  assert.ok(parseContact({ ...VALID, message: "x".repeat(MAX_MESSAGE) }).ok);
});

test("contact topics: only the four known values", () => {
  assert.ok(isContactTopic("press"));
  assert.ok(!isContactTopic("PRESS"));
});

test("contact: stores the row", async () => {
  const { db, sql, bound } = fakeDb();
  const res = await handleContact(VALID, { db, log: () => {} });
  assert.deepEqual(res, { status: 200, body: { ok: true } });
  assert.match(sql[0], /INSERT INTO contact_messages/);
  assert.deepEqual(bound[0], ["shop", "Ana Ruiz", "ana@shop.com", "Ana's Tacos", "Hi!", null, null, null, null]);
});

test("contact: invalid input gives 400 and stores nothing", async () => {
  const { db, bound } = fakeDb();
  assert.deepEqual(await handleContact({ ...VALID, email: "" }, { db, log: () => {} }), {
    status: 400,
    body: { error: "invalid_email" },
  });
  assert.equal(bound.length, 0);
});

test("contact: honeypot answers ok and stores nothing", async () => {
  const { db, bound } = fakeDb();
  assert.deepEqual(await handleContact({ ...VALID, website: "spam.example" }, { db, log: () => {} }), {
    status: 200,
    body: { ok: true },
  });
  assert.equal(bound.length, 0);
});

test("contact: missing DB gives 503", async () => {
  const logged: string[] = [];
  assert.deepEqual(await handleContact(VALID, { db: undefined, log: (m) => logged.push(m) }), {
    status: 503,
    body: { error: "unavailable" },
  });
  assert.equal(logged.length, 1);
});

test("contact: insert failure gives 500 and never logs the email or message", async () => {
  const { db } = fakeDb(true);
  const logged: string[] = [];
  assert.deepEqual(await handleContact(VALID, { db, log: (m) => logged.push(m) }), {
    status: 500,
    body: { error: "server" },
  });
  assert.ok(logged[0].includes("TypeError") && !logged[0].includes("ana@shop.com") && !logged[0].includes("Hi!"));
});
