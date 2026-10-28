import { test } from "node:test";
import assert from "node:assert/strict";
import { checkAddress } from "../src/server/check-address.ts";
import { GeocoderError, type FetchFn } from "../src/server/geocode.ts";

function fakeJson(body: unknown): FetchFn {
  return () => Promise.resolve(Response.json(body));
}

test("inside point", async () =>
  assert.deepEqual(await checkAddress("University Village", fakeJson([{ lat: "47.6632", lon: "-122.2990" }])), {
    found: true,
    inArea: true,
    lat: 47.6632,
    lng: -122.299,
  }));

test("outside point", async () => {
  const r = await checkAddress("Green Lake", fakeJson([{ lat: "47.68", lon: "-122.327" }]));
  assert.ok(r.found && !r.inArea);
});

test("no result is not found", async () => assert.deepEqual(await checkAddress("asdfgh", fakeJson([])), { found: false }));

test("request is bounded to Seattle", async () => {
  let url = "";
  await checkAddress("Main St", (u) => {
    url = u;
    return Promise.resolve(Response.json([]));
  });
  assert.match(url, /bounded=1/);
  assert.match(url, /viewbox=-122\.44,47\.74,-122\.23,47\.49/);
  assert.match(url, /q=Main%20St/);
});

test("request sends a User-Agent and a timeout signal", async () => {
  let init: RequestInit | undefined;
  await checkAddress("Main St", (_u, i) => {
    init = i;
    return Promise.resolve(Response.json([]));
  });
  assert.ok(init?.signal instanceof AbortSignal);
  assert.match(new Headers(init?.headers).get("User-Agent") ?? "", /^PacketLanding\/1\.0/);
});

test("5xx throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.resolve(new Response("", { status: 503 }))), GeocoderError));
test("429 throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.resolve(new Response("", { status: 429 }))), GeocoderError));
test("network failure throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.reject(new DOMException("timeout", "TimeoutError"))), GeocoderError));
test("malformed body throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", fakeJson({ nope: 1 })), GeocoderError));
test("non-JSON body throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.resolve(new Response("<html>", { status: 200 }))), GeocoderError));
test("non-numeric coordinates throw GeocoderError", async () =>
  assert.rejects(checkAddress("x", fakeJson([{ lat: "abc", lon: "-122.3" }])), GeocoderError));
