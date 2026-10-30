import { test } from "node:test";
import assert from "node:assert/strict";
import { normalizeStreet, parseCrossStreets } from "../src/lib/street-names.ts";

const key = (raw: string): string => normalizeStreet(raw).key;

test("45th St spellings share one key", () => {
  for (const raw of ["NE 45th Street", "45th St NE", "Northeast 45th St", "N.E. 45th St."]) {
    assert.equal(key(raw), "45th st ne", raw);
  }
});

test("Brooklyn Avenue Northeast equals Brooklyn Ave NE", () =>
  assert.equal(key("Brooklyn Avenue Northeast"), key("Brooklyn Ave NE")));

test("a bare number gets its ordinal", () => assert.equal(key("45 St NE"), key("45th St NE")));

test("ordinal suffixes", () => {
  const cases: [string, string][] = [
    ["1", "1st"], ["2", "2nd"], ["3", "3rd"], ["4", "4th"], ["11", "11th"], ["12", "12th"],
    ["13", "13th"], ["21", "21st"], ["22", "22nd"], ["101", "101st"], ["111", "111th"],
  ];
  for (const [bare, ordinal] of cases) assert.equal(key(`${bare} Ave`), `${ordinal} ave`, bare);
});

test("word ordinals map to numbers", () => {
  assert.equal(key("First Ave NE"), "1st ave ne");
  assert.equal(key("Twelfth Ave NE"), "12th ave ne");
});

test("suffixes", () => {
  assert.equal(key("Montlake Boulevard"), "montlake blvd");
  assert.equal(key("Mason Place"), "mason pl");
  assert.equal(key("University Way"), "university way");
});

test("E 45th St and NE 45th St stay distinct", () => assert.notEqual(key("E 45th St"), key("NE 45th St")));

test("core drops directionals and the suffix", () => {
  assert.equal(normalizeStreet("NE 45th St").core, "45th");
  assert.equal(normalizeStreet("Brooklyn Ave NE").core, "brooklyn");
});

test("every separator gives the same pair", () => {
  const expected = ["NE 45th St", "Brooklyn Ave NE"];
  for (const q of [
    "NE 45th St and Brooklyn Ave NE",
    "NE 45th St & Brooklyn Ave NE",
    "NE 45th St&Brooklyn Ave NE",
    "NE 45th St at Brooklyn Ave NE",
    "NE 45th St @ Brooklyn Ave NE",
    "NE 45th St / Brooklyn Ave NE",
    "NE 45th St AND Brooklyn Ave NE",
  ]) {
    assert.deepEqual(parseCrossStreets(q), expected, q);
  }
});

test("locality suffixes are stripped", () => {
  for (const suffix of [", Seattle", ", Seattle, WA", ", Seattle WA 98105", ", WA"]) {
    assert.deepEqual(parseCrossStreets(`NE 45th St and Brooklyn Ave NE${suffix}`), ["NE 45th St", "Brooklyn Ave NE"], suffix);
  }
});

test("queries that are not two streets give null", () => {
  for (const q of ["A St and B St and C St", "4500 Brooklyn Ave NE", "Pratt Park", "Grand Ave", "", "and Brooklyn Ave NE"]) {
    assert.equal(parseCrossStreets(q), null, q);
  }
});
