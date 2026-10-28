import type { LatLng } from "../lib/geo.ts";

/**
 * First draft, clockwise. Traces the simulator drop-offs (Ave housing, Mercer
 * Court, north campus dorms, Bryant homes, U Village hub) with about 250 m of margin.
 * TODO: Tanner reviews this polygon before launch.
 */
export const SERVICE_AREA: readonly LatLng[] = [
  [47.6700, -122.3175], [47.6725, -122.2990], [47.6700, -122.2920], [47.6620, -122.2930],
  [47.6580, -122.3000], [47.6540, -122.3080], [47.6540, -122.3175],
];

export const U_VILLAGE: LatLng = [47.6632, -122.2990];

/** Seattle bounding box used to bound geocoder lookups. */
export const SEATTLE_BOX = { west: -122.44, south: 47.49, east: -122.23, north: 47.74 };
