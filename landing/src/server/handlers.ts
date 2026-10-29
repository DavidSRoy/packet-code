import { round } from "../lib/geo.ts";
import { parseQuery, parseSignup } from "../lib/signup-input.ts";
import { checkAddress, type CheckResult } from "./check-address.ts";
import { GeocoderError, type FetchFn } from "./geocode.ts";
import type { IntersectionIndex } from "./intersections.ts";
import { upsertSignup, type SignupDb } from "./signups.ts";

export interface Deps {
  db: SignupDb | undefined;
  fetchFn: FetchFn;
  intersections: IntersectionIndex;
  log: (msg: string) => void;
}

export interface HandlerResult {
  status: number;
  body: object;
}

export async function handleCheck(body: unknown, deps: Deps): Promise<HandlerResult> {
  const parsed = parseQuery(body);
  if (!parsed.ok) return { status: 400, body: { error: parsed.error } };
  let result: CheckResult;
  try {
    result = await checkAddress(parsed.q, deps.fetchFn, deps.intersections);
  } catch (e) {
    if (!(e instanceof GeocoderError)) throw e;
    deps.log(`[Check:POST] Geocoder failed — ${JSON.stringify({ reason: e.message })}`);
    return { status: 502, body: { error: "geocoder" } };
  }
  if (!result.found) return { status: 200, body: { found: false } };
  return {
    status: 200,
    body: { found: true, inArea: result.inArea, lat: round(result.lat, 3), lng: round(result.lng, 3) },
  };
}

export async function handleSignup(body: unknown, deps: Deps): Promise<HandlerResult> {
  const parsed = parseSignup(body);
  if (!parsed.ok) return { status: 400, body: { error: parsed.error } };
  const input = parsed.value;
  if (!deps.db) {
    deps.log("[Signup:POST] DB binding missing");
    return { status: 503, body: { error: "unavailable" } };
  }

  let inArea: boolean | null = null;
  let lat: number | null = null;
  let lng: number | null = null;
  if (input.q !== null) {
    try {
      const result = await checkAddress(input.q, deps.fetchFn, deps.intersections);
      if (result.found) {
        inArea = result.inArea;
        lat = round(result.lat, 2);
        lng = round(result.lng, 2);
      }
    } catch (e) {
      if (!(e instanceof GeocoderError)) throw e;
      // The sign-up is never lost to a geocoder outage: save the email without a location.
      deps.log(`[Signup:POST] Geocoder failed, saving without location — ${JSON.stringify({ reason: e.message })}`);
    }
  }

  try {
    await upsertSignup(deps.db, {
      email: input.email,
      inArea,
      lat,
      lng,
      utmSource: input.utmSource,
      utmMedium: input.utmMedium,
      utmCampaign: input.utmCampaign,
      referrer: input.referrer,
    });
  } catch (e) {
    // D1 error names carry no bound values, so the name is safe to log.
    const error = e instanceof Error ? e.name : "unknown";
    deps.log(`[Signup:POST] Insert failed — ${JSON.stringify({ in_area: inArea, utm_source: input.utmSource, error })}`);
    return { status: 500, body: { error: "server" } };
  }
  return { status: 200, body: { ok: true } };
}
