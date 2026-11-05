/**
 * Street-name normalisation for cross-street lookups. Pure, no imports, so the
 * server and scripts/fetch-intersections.mjs share one definition.
 */

const DIRECTIONALS: Readonly<Record<string, string>> = {
  northeast: "ne", northwest: "nw", southeast: "se", southwest: "sw",
  north: "n", south: "s", east: "e", west: "w",
  ne: "ne", nw: "nw", se: "se", sw: "sw", n: "n", s: "s", e: "e", w: "w",
};

const SUFFIXES: Readonly<Record<string, string>> = {
  street: "st", str: "st", st: "st",
  avenue: "ave", av: "ave", ave: "ave",
  boulevard: "blvd", blv: "blvd", blvd: "blvd",
  place: "pl", pl: "pl",
  way: "way",
  drive: "dr", dr: "dr",
  road: "rd", rd: "rd",
  lane: "ln", ln: "ln",
  court: "ct", ct: "ct",
  terrace: "ter", ter: "ter",
  parkway: "pkwy", pkwy: "pkwy",
  circle: "cir", cir: "cir",
};

const WORD_ORDINALS: Readonly<Record<string, string>> = {
  first: "1st", second: "2nd", third: "3rd", fourth: "4th", fifth: "5th", sixth: "6th",
  seventh: "7th", eighth: "8th", ninth: "9th", tenth: "10th", eleventh: "11th", twelfth: "12th",
};

function ordinal(n: string): string {
  const lastTwo = Number(n) % 100;
  if (lastTwo >= 11 && lastTwo <= 13) return `${n}th`;
  const last = Number(n) % 10;
  if (last === 1) return `${n}st`;
  if (last === 2) return `${n}nd`;
  if (last === 3) return `${n}rd`;
  return `${n}th`;
}

function mapToken(token: string): string {
  if (/^\d+$/.test(token)) return ordinal(token);
  return WORD_ORDINALS[token] ?? SUFFIXES[token] ?? token;
}

export interface NormalizedStreet {
  /** Full comparable form, directionals moved to the end: "45th st ne". */
  key: string;
  /** Name without directionals or a trailing suffix: "45th", "brooklyn". */
  core: string;
}

export function normalizeStreet(raw: string): NormalizedStreet {
  const tokens = raw.toLowerCase().replace(/\./g, "").replace(/,/g, " ").trim().split(/\s+/).filter(Boolean);
  const rest: string[] = [];
  const dirs: string[] = [];
  for (const token of tokens) {
    const dir = DIRECTIONALS[token];
    if (dir) dirs.push(dir);
    else rest.push(mapToken(token));
  }
  const last = rest.at(-1);
  const coreTokens = rest.length > 1 && last !== undefined && last in SUFFIXES ? rest.slice(0, -1) : rest;
  return { key: [...rest, ...dirs.sort()].join(" "), core: coreTokens.join(" ") };
}

const SEATTLE_SUFFIX = /(?:,\s*|\s+)seattle(?:\s*,?\s*(?:wa|washington))?(?:\s+\d{5})?\s*$/i;
const STATE_SUFFIX = /(?:,\s*|\s+)(?:wa|washington)(?:\s+\d{5})?\s*$/i;
const SEPARATOR = /\s+(?:and|at)\s+|\s*[&@/]\s*/i;

/** Splits "A and B" (or &, at, @, /) into two street names. Null for anything else. */
export function parseCrossStreets(q: string): [string, string] | null {
  const trimmed = q.replace(SEATTLE_SUFFIX, "").replace(STATE_SUFFIX, "");
  const parts = trimmed.split(SEPARATOR).map((part) => part.trim());
  if (parts.length !== 2) return null;
  const [a, b] = parts;
  if (!a || !b) return null;
  return [a, b];
}
