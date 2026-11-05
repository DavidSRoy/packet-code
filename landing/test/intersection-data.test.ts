import { test } from "node:test";
import assert from "node:assert/strict";
import { INTERSECTIONS } from "../src/server/intersection-index.ts";
import { findIntersection } from "../src/server/intersections.ts";
import { pointInPolygon } from "../src/lib/geo.ts";
import { SERVICE_AREA } from "../src/config/service-area.ts";

test("NE 45th St and Brooklyn Ave NE is found and inside the service area", () => {
  for (const q of ["NE 45th St and Brooklyn Ave NE", "NE 45th St & Brooklyn Ave NE", "NE 45th St and Brooklyn Ave NE, Seattle"]) {
    const point = findIntersection(q, INTERSECTIONS);
    assert.ok(point, q);
    assert.equal(pointInPolygon(point, SERVICE_AREA), true, q);
  }
});

test("the hint's example, NE 45th St and 25th Ave NE, is found", () =>
  assert.ok(findIntersection("NE 45th St and 25th Ave NE", INTERSECTIONS)));
