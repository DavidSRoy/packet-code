import { SERVICE_AREA } from "../config/service-area.ts";
import { pointInPolygon } from "../lib/geo.ts";
import { geocode, type FetchFn } from "./geocode.ts";

export type CheckResult = { found: false } | { found: true; inArea: boolean; lat: number; lng: number };

export async function checkAddress(q: string, fetchFn: FetchFn): Promise<CheckResult> {
  const point = await geocode(q, fetchFn);
  if (!point) return { found: false };
  const [lat, lng] = point;
  return { found: true, inArea: pointInPolygon(point, SERVICE_AREA), lat, lng };
}
