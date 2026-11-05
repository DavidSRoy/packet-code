import { SERVICE_AREA } from "../config/service-area.ts";
import { pointInPolygon } from "../lib/geo.ts";
import { geocode, type FetchFn } from "./geocode.ts";
import { findIntersection, type IntersectionIndex } from "./intersections.ts";

export type CheckResult = { found: false } | { found: true; inArea: boolean; lat: number; lng: number };

/** Cross streets resolve from local OSM data first; everything else goes to the geocoder. */
export async function checkAddress(q: string, fetchFn: FetchFn, index: IntersectionIndex): Promise<CheckResult> {
  const point = findIntersection(q, index) ?? (await geocode(q, fetchFn));
  if (!point) return { found: false };
  const [lat, lng] = point;
  return { found: true, inArea: pointInPolygon(point, SERVICE_AREA), lat, lng };
}
