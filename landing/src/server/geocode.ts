import type { LatLng } from "../lib/geo.ts";
import { SEATTLE_BOX } from "../config/service-area.ts";

export type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

export class GeocoderError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "GeocoderError";
  }
}

const TIMEOUT_MS = 6000;
const USER_AGENT = "PacketLanding/1.0 (+[CONTACT EMAIL])";

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function parseHit(hit: unknown): LatLng {
  if (!isRecord(hit) || typeof hit.lat !== "string" || typeof hit.lon !== "string") {
    throw new GeocoderError("[Geocoder:parseHit] Unexpected result shape");
  }
  const lat = Number(hit.lat);
  const lng = Number(hit.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    throw new GeocoderError("[Geocoder:parseHit] Non-numeric coordinates");
  }
  return [lat, lng];
}

/** Looks up `q` inside the Seattle box. Resolves null when nothing matches. */
export async function geocode(q: string, fetchFn: FetchFn): Promise<LatLng | null> {
  const { west, north, east, south } = SEATTLE_BOX;
  const url =
    "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=us&bounded=1" +
    `&viewbox=${west},${north},${east},${south}&q=${encodeURIComponent(q)}`;

  let res: Response;
  try {
    res = await fetchFn(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    throw new GeocoderError("[Geocoder:geocode] Request failed", { cause: err });
  }
  if (!res.ok) throw new GeocoderError(`[Geocoder:geocode] Upstream status — {status: ${res.status}}`);

  let body: unknown;
  try {
    body = await res.json();
  } catch (err) {
    throw new GeocoderError("[Geocoder:geocode] Body is not JSON", { cause: err });
  }
  if (!Array.isArray(body)) throw new GeocoderError("[Geocoder:geocode] Body is not an array");
  if (body.length === 0) return null;
  return parseHit(body[0]);
}
