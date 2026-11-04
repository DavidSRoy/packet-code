import { test } from "node:test";
import assert from "node:assert/strict";
import { pinProgress, sliceAt, sliceFill } from "../src/lib/pin.ts";

// A section 3 screens tall (length 2) in a 900px viewport travels 1800px while pinned.
test("pinProgress is 0 before the section reaches the top", () => assert.equal(pinProgress(300, 2700, 900), 0));
test("pinProgress is 0 as the stage pins", () => assert.equal(pinProgress(0, 2700, 900), 0));
test("pinProgress is halfway through the travel", () => assert.equal(pinProgress(-900, 2700, 900), 0.5));
test("pinProgress is 1 as the stage unpins and after", () => {
	assert.equal(pinProgress(-1800, 2700, 900), 1);
	assert.equal(pinProgress(-5000, 2700, 900), 1);
});
test("pinProgress is 1 when the section is no taller than the viewport", () => assert.equal(pinProgress(-10, 900, 900), 1));

test("sliceAt splits progress into equal slices", () => {
	assert.equal(sliceAt(0, 3), 0);
	assert.equal(sliceAt(0.33, 3), 0);
	assert.equal(sliceAt(0.34, 3), 1);
	assert.equal(sliceAt(0.99, 3), 2);
});
test("sliceAt keeps the last slice at progress 1", () => assert.equal(sliceAt(1, 3), 2));

test("sliceFill is how far through its own slice progress is", () => {
	assert.equal(sliceFill(0.5, 1, 2), 0);
	assert.equal(sliceFill(0.75, 1, 2), 0.5);
	assert.equal(sliceFill(1, 1, 2), 1);
});
test("sliceFill is 0 before the slice and 1 after it", () => {
	assert.equal(sliceFill(0.1, 1, 2), 0);
	assert.equal(sliceFill(0.9, 0, 2), 1);
});
