import { test } from "node:test";
import assert from "node:assert/strict";
import { checkAddress } from "../src/server/check-address.ts";
import { GeocoderError, type FetchFn } from "../src/server/geocode.ts";
import { buildIndex } from "../src/server/intersections.ts";

const EMPTY = buildIndex({ names: [], points: [] });
const FIXTURE = buildIndex({ names: ["Northeast 45th Street", "Brooklyn Avenue Northeast"], points: [[0, 1, 47.66129, -122.31429]] });

function fakeJson(body: unknown): FetchFn {
  return () => Promise.resolve(Response.json(body));
}

test("inside point", async () =>
  assert.deepEqual(await checkAddress("University Village", fakeJson([{ lat: "47.6632", lon: "-122.2990" }]), EMPTY), {
    found: true,
    inArea: true,
    lat: 47.6632,
    lng: -122.299,
  }));

test("outside point", async () => {
  const r = await checkAddress("Green Lake", fakeJson([{ lat: "47.68", lon: "-122.327" }]), EMPTY);
  assert.ok(r.found && !r.inArea);
});

test("no result is not found", async () => assert.deepEqual(await checkAddress("asdfgh", fakeJson([]), EMPTY), { found: false }));

test("request is bounded to Seattle", async () => {
  let url = "";
  await checkAddress("Main St", (u) => {
    url = u;
    return Promise.resolve(Response.json([]));
  }, EMPTY);
  assert.match(url, /bounded=1/);
  assert.match(url, /viewbox=-122\.44,47\.74,-122\.23,47\.49/);
  assert.match(url, /q=Main%20St/);
});

test("request sends a User-Agent and a timeout signal", async () => {
  let init: RequestInit | undefined;
  await checkAddress("Main St", (_u, i) => {
    init = i;
    return Promise.resolve(Response.json([]));
  }, EMPTY);
  assert.ok(init?.signal instanceof AbortSignal);
  assert.match(new Headers(init?.headers).get("User-Agent") ?? "", /^PacketLanding\/1\.0/);
});

test("5xx throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.resolve(new Response("", { status: 503 })), EMPTY), GeocoderError));
test("429 throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.resolve(new Response("", { status: 429 })), EMPTY), GeocoderError));
test("network failure throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.reject(new DOMException("timeout", "TimeoutError")), EMPTY), GeocoderError));
test("malformed body throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", fakeJson({ nope: 1 }), EMPTY), GeocoderError));
test("non-JSON body throws GeocoderError", async () =>
  assert.rejects(checkAddress("x", () => Promise.resolve(new Response("<html>", { status: 200 })), EMPTY), GeocoderError));
test("non-numeric coordinates throw GeocoderError", async () =>
  assert.rejects(checkAddress("x", fakeJson([{ lat: "abc", lon: "-122.3" }]), EMPTY), GeocoderError));

test("a cross-street hit resolves locally without calling the geocoder", async () =>
  assert.deepEqual(
    await checkAddress("NE 45th St and Brooklyn Ave NE", () => Promise.reject(new Error("geocoder called")), FIXTURE),
    { found: true, inArea: true, lat: 47.66129, lng: -122.31429 },
  ));

test("a cross-street miss falls through to the geocoder", async () => {
  let isCalled = false;
  const r = await checkAddress("NE 45th St and 25th Ave NE", () => {
    isCalled = true;
    return Promise.resolve(Response.json([{ lat: "47.6613", lon: "-122.3009" }]));
  }, FIXTURE);
  assert.equal(isCalled, true);
  assert.ok(r.found && r.inArea);
});

test("GeocoderError carries its own name", async () =>
  assert.rejects(checkAddress("x", fakeJson({ nope: 1 }), EMPTY), { name: "GeocoderError" }));
