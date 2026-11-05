import { test } from "node:test";
import assert from "node:assert/strict";
import {
  handleCheck,
  handleSignup,
  type Deps,
} from "../src/server/handlers.ts";
import type { SignupDb } from "../src/server/signups.ts";
import { buildIndex } from "../src/server/intersections.ts";

interface Options {
  geo?: [number, number];
  geoFails?: boolean;
  dbFails?: boolean;
  db?: undefined;
}

interface TestDeps extends Deps {
  sql: string[];
  bound: unknown[][];
  logged: string[];
}

function deps(options: Options = {}): TestDeps {
  const bound: unknown[][] = [];
  const logged: string[] = [];
  const sql: string[] = [];
  const db: SignupDb = {
    prepare: (text) => {
      sql.push(text);
      return {
        bind: (...values) => ({
          run: () => {
            if (options.dbFails) return Promise.reject(new Error("boom"));
            bound.push(values);
            return Promise.resolve({});
          },
        }),
      };
    },
  };
  return {
    db: "db" in options ? options.db : db,
    fetchFn: () => {
      if (options.geoFails) return Promise.reject(new Error("down"));
      const hits = options.geo
        ? [{ lat: String(options.geo[0]), lon: String(options.geo[1]) }]
        : [];
      return Promise.resolve(Response.json(hits));
    },
    intersections: buildIndex({ names: [], points: [] }),
    log: (msg) => logged.push(msg),
    sql,
    bound,
    logged,
  };
}

test("check: bad query gives 400", async () =>
  assert.deepEqual(await handleCheck({ q: "" }, deps()), {
    status: 400,
    body: { error: "invalid_query" },
  }));

test("check: found rounds to 3 decimals", async () =>
  assert.deepEqual(
    await handleCheck(
      { q: "U Village" },
      deps({ geo: [47.66391, -122.29971] }),
    ),
    {
      status: 200,
      body: { found: true, inArea: true, lat: 47.664, lng: -122.3 },
    },
  ));

test("check: not found", async () =>
  assert.deepEqual(await handleCheck({ q: "zzz" }, deps()), {
    status: 200,
    body: { found: false },
  }));

test("check: geocoder failure gives 502", async () =>
  assert.equal(
    (await handleCheck({ q: "x" }, deps({ geoFails: true }))).status,
    502,
  ));

test("signup: bad email gives 400", async () =>
  assert.deepEqual(await handleSignup({ email: "no" }, deps()), {
    status: 400,
    body: { error: "invalid_email" },
  }));

test("signup: missing DB gives 503 and logs", async () => {
  const d = deps({ db: undefined });
  assert.equal((await handleSignup({ email: "a@b.co" }, d)).status, 503);
  assert.match(d.logged[0], /^\[Signup:POST\] DB binding missing/);
});

test("signup: stores in_area and 2-decimal location, never the address", async () => {
  const d = deps({ geo: [47.66391, -122.29971] });
  assert.deepEqual(
    await handleSignup(
      { email: "A@b.co", q: "4500 25th Ave NE", utm_source: "flyer" },
      d,
    ),
    {
      status: 200,
      body: { ok: true },
    },
  );
  assert.deepEqual(d.bound[0], [
    "a@b.co",
    1,
    47.66,
    -122.3,
    "flyer",
    null,
    null,
    null,
  ]);
  assert.ok(!JSON.stringify(d.bound).includes("25th"));
});

test("signup: no q stores null in_area", async () => {
  const d = deps();
  await handleSignup({ email: "a@b.co" }, d);
  assert.equal(d.bound[0][1], null);
});

test("signup: geocoder down still saves the email with null in_area", async () => {
  const d = deps({ geoFails: true });
  assert.equal(
    (await handleSignup({ email: "a@b.co", q: "x" }, d)).status,
    200,
  );
  assert.equal(d.bound[0][1], null);
});

test("signup: insert failure gives 500 without the email in the log", async () => {
  const d = deps({ dbFails: true });
  assert.equal((await handleSignup({ email: "a@b.co" }, d)).status, 500);
  assert.ok(!d.logged[0].includes("a@b.co"));
  assert.match(d.logged[0], /^\[Signup:POST\] Insert failed — /);
});

test("signup: upsert keeps first non-null values (existing column wins)", async () => {
  const d = deps();
  await handleSignup({ email: "a@b.co" }, d);
  assert.match(d.sql[0], /in_area=COALESCE\(in_area,excluded\.in_area\)/);
  assert.match(
    d.sql[0],
    /utm_source=COALESCE\(utm_source,excluded\.utm_source\)/,
  );
  assert.ok(!d.sql[0].includes("COALESCE(excluded."));
});

test("check: geocoder failure logs the reason, never the query", async () => {
  const d = deps({ geoFails: true });
  await handleCheck({ q: "4500 25th Ave NE" }, d);
  assert.equal(d.logged[0], '[Check:POST] Geocoder failed — {"reason":"[Geocoder:geocode] Request failed"}');
});

test("signup: geocoder failure logs the reason, never the address", async () => {
  const d = deps({ geoFails: true });
  await handleSignup({ email: "a@b.co", q: "4500 25th Ave NE" }, d);
  assert.match(d.logged[0], /^\[Signup:POST\] Geocoder failed, saving without location — \{"reason":"\[Geocoder:geocode\] Request failed"\}$/);
  assert.ok(!d.logged[0].includes("25th"));
});

test("signup: insert failure logs the error name", async () => {
  const d = deps({ dbFails: true });
  await handleSignup({ email: "a@b.co", utm_source: "flyer" }, d);
  assert.equal(d.logged[0], '[Signup:POST] Insert failed — {"in_area":null,"utm_source":"flyer","error":"Error"}');
});

test("signup: an outside address stores in_area 0", async () => {
  const d = deps({ geo: [47.68, -122.327] });
  await handleSignup({ email: "a@b.co", q: "Green Lake" }, d);
  assert.deepEqual(d.bound[0].slice(1, 4), [0, 47.68, -122.33]);
});

test("signup: a not-found address stores null in_area, lat and lng", async () => {
  const d = deps();
  assert.equal((await handleSignup({ email: "a@b.co", q: "asdfgh" }, d)).status, 200);
  assert.deepEqual(d.bound[0].slice(1, 4), [null, null, null]);
});
