import { test } from "node:test";
import assert from "node:assert/strict";
import { distanceKm, pointInPolygon, round } from "../src/lib/geo.ts";
import { SERVICE_AREA } from "../src/config/service-area.ts";

test("U Village is inside", () => assert.equal(pointInPolygon([47.6632, -122.2990], SERVICE_AREA), true));
test("NE 45th St and Brooklyn Ave NE is inside", () => assert.equal(pointInPolygon([47.6614, -122.3140], SERVICE_AREA), true));
test("Green Lake is outside", () => assert.equal(pointInPolygon([47.6800, -122.3270], SERVICE_AREA), false));
test("Laurelhurst is outside", () => assert.equal(pointInPolygon([47.6625, -122.2780], SERVICE_AREA), false));
test("round", () => { assert.equal(round(47.66391, 2), 47.66); assert.equal(round(-122.29971, 3), -122.3); });
test("distanceKm: 0.01 deg of latitude is about 1.11 km", () => {
  const d = distanceKm([47.66, -122.3], [47.67, -122.3]);
  assert.ok(Math.abs(d - 1.112) < 0.01);
});
test("distanceKm: Green Lake is beyond 2.5 km of U Village", () => assert.ok(distanceKm([47.68, -122.327], [47.6632, -122.299]) > 2.5));
