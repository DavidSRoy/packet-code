import { test } from "node:test";
import assert from "node:assert/strict";
import { lockProgress, ramp } from "../src/lib/lock.ts";

test("lockProgress: 0 while the section's top is at or below the viewport top", () => {
	assert.equal(lockProgress(400, 2700, 900), 0);
	assert.equal(lockProgress(0, 2700, 900), 0);
});
test("lockProgress: halfway through the scrollable span", () => {
	assert.equal(lockProgress(-900, 2700, 900), 0.5);
});
test("lockProgress: 1 once the bottom reaches the viewport bottom, and stays there", () => {
	assert.equal(lockProgress(-1800, 2700, 900), 1);
	assert.equal(lockProgress(-2400, 2700, 900), 1);
});
test("lockProgress: a section no taller than the viewport is always at the end", () => {
	assert.equal(lockProgress(300, 900, 900), 1);
	assert.equal(lockProgress(-100, 600, 900), 1);
});
test("ramp: clamps across a band", () => {
	assert.equal(ramp(0.1, 0.36, 0.46), 0);
	assert.ok(Math.abs(ramp(0.41, 0.36, 0.46) - 0.5) < 1e-9);
	assert.equal(ramp(0.9, 0.36, 0.46), 1);
});
test("ramp: a degenerate band steps at its edge", () => {
	assert.equal(ramp(0.3, 0.5, 0.5), 0);
	assert.equal(ramp(0.5, 0.5, 0.5), 1);
});
