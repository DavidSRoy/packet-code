import type { LatLng } from "../lib/geo.ts";
import { normalizeStreet, parseCrossStreets } from "../lib/street-names.ts";

export type IntersectionPoint = readonly [nameA: number, nameB: number, lat: number, lng: number];

export interface IntersectionData {
  names: readonly string[];
  points: readonly IntersectionPoint[];
}

export interface IntersectionIndex {
  exact: ReadonlyMap<string, LatLng>;
  loose: ReadonlyMap<string, LatLng | "ambiguous">;
}

function isPoint(v: unknown): v is IntersectionPoint {
  return Array.isArray(v) && v.length === 4 && v.every((n) => typeof n === "number" && Number.isFinite(n));
}

export function isIntersectionData(v: unknown): v is IntersectionData {
  if (typeof v !== "object" || v === null || !("names" in v) || !("points" in v)) return false;
  const { names, points } = v;
  return (
    Array.isArray(names) &&
    names.every((n) => typeof n === "string") &&
    Array.isArray(points) &&
    points.every(isPoint)
  );
}

function pairKey(a: string, b: string): string {
  return [a, b].sort().join("|");
}

/** Builds the exact and loose lookup maps. First write wins on exact keys. */
export function buildIndex(data: IntersectionData): IntersectionIndex {
  const exact = new Map<string, LatLng>();
  const loose = new Map<string, LatLng | "ambiguous">();
  const looseOwner = new Map<string, string>();
  for (const [ia, ib, lat, lng] of data.points) {
    const nameA = data.names[ia];
    const nameB = data.names[ib];
    if (nameA === undefined || nameB === undefined) continue;
    const a = normalizeStreet(nameA);
    const b = normalizeStreet(nameB);
    const exactKey = pairKey(a.key, b.key);
    if (exact.has(exactKey)) continue;
    const point: LatLng = [lat, lng];
    exact.set(exactKey, point);

    // A loose key is usable only while one street pair owns it.
    const looseKey = pairKey(a.core, b.core);
    const owner = looseOwner.get(looseKey);
    if (owner === undefined) {
      looseOwner.set(looseKey, exactKey);
      loose.set(looseKey, point);
    } else if (owner !== exactKey) {
      loose.set(looseKey, "ambiguous");
    }
  }
  return { exact, loose };
}

/** Resolves "A and B" style queries to an intersection point, or null. */
export function findIntersection(q: string, index: IntersectionIndex): LatLng | null {
  const pair = parseCrossStreets(q);
  if (!pair) return null;
  const a = normalizeStreet(pair[0]);
  const b = normalizeStreet(pair[1]);
  const hit = index.exact.get(pairKey(a.key, b.key));
  if (hit) return hit;
  const loose = index.loose.get(pairKey(a.core, b.core));
  return loose === undefined || loose === "ambiguous" ? null : loose;
}
