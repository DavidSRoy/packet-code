import { test } from "node:test";
import assert from "node:assert/strict";
import { areaPath, PLAN_H, PLAN_W, places, projectPlan, streetsPath } from "../src/lib/plan.ts";
import { SERVICE_AREA, U_VILLAGE } from "../src/config/service-area.ts";

test("projectPlan: the U Village hub lands inside the plan, right of centre and above the middle", () => {
	const [x, y] = projectPlan(U_VILLAGE);
	assert.ok(x > PLAN_W / 2 && x < PLAN_W);
	assert.ok(y > 0 && y < PLAN_H / 2 + 20);
});
test("projectPlan: north is up and east is right", () => {
	const [x0, y0] = projectPlan([47.66, -122.3]);
	const [x1, y1] = projectPlan([47.67, -122.29]);
	assert.ok(y1 < y0);
	assert.ok(x1 > x0);
});
test("areaPath: one closed path through every vertex of the service area", () => {
	const d = areaPath(SERVICE_AREA);
	assert.ok(d.startsWith("M") && d.endsWith("Z"));
	assert.equal(d.split("L").length, SERVICE_AREA.length);
});
test("streetsPath: keeps polylines that touch the plan and drops the rest", () => {
	const inside = [[47.6632, -122.299], [47.664, -122.298]] as const;
	const farAway = [[47.5, -122.5], [47.51, -122.5]] as const;
	const d = streetsPath([inside, farAway]);
	assert.equal(d.split("M").length - 1, 1);
});
test("places: projects and keeps the step", () => {
	const [p] = places([{ name: "Hub", at: U_VILLAGE, step: 1 }]);
	assert.equal(p.name, "Hub");
	assert.equal(p.step, 1);
	assert.ok(p.x > 0 && p.y > 0);
});
