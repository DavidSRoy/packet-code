import { test } from "node:test";
import assert from "node:assert/strict";
import { buildIndex, findIntersection, isIntersectionData } from "../src/server/intersections.ts";

const index = buildIndex({
  names: ["Northeast 45th Street", "Brooklyn Avenue Northeast", "Northeast 50th Street", "Roosevelt Way Northeast", "Northeast 50th Place"],
  points: [
    [0, 1, 47.66135, -122.31416],
    [2, 3, 47.66485, -122.31766],
    [4, 3, 47.66530, -122.31766],
  ],
});

test("exact match in both name orders", () => {
  assert.deepEqual(findIntersection("NE 45th St and Brooklyn Ave NE", index), [47.66135, -122.31416]);
  assert.deepEqual(findIntersection("Brooklyn Ave NE & NE 45th St", index), [47.66135, -122.31416]);
});

test("unique loose match", () => assert.deepEqual(findIntersection("45th and Brooklyn", index), [47.66135, -122.31416]));

test("ambiguous loose match is null", () => assert.equal(findIntersection("50th and Roosevelt", index), null));

test("exact match still wins where loose is ambiguous", () =>
  assert.deepEqual(findIntersection("NE 50th Pl and Roosevelt Way NE", index), [47.6653, -122.31766]));

test("miss is null", () => {
  assert.equal(findIntersection("NE 45th St and 25th Ave NE", index), null);
  assert.equal(findIntersection("4500 Brooklyn Ave NE", index), null);
});

test("type guard rejects bad shapes", () => {
  assert.equal(isIntersectionData({ names: ["a"], points: [[0, 1, 2]] }), false);
  assert.equal(isIntersectionData({ names: [1], points: [] }), false);
  assert.equal(isIntersectionData({ names: ["a", "b"], points: [[0, 1, 47.6, -122.3]] }), true);
});
