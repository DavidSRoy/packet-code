export type LatLng = readonly [lat: number, lng: number];

/** Ray casting: counts how many polygon edges a ray from `p` toward +lng crosses. */
export function pointInPolygon(p: LatLng, poly: readonly LatLng[]): boolean {
  const [lat, lng] = p;
  let isInside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [latI, lngI] = poly[i];
    const [latJ, lngJ] = poly[j];
    const doesCross = latI > lat !== latJ > lat && lng < ((lngJ - lngI) * (lat - latI)) / (latJ - latI) + lngI;
    if (doesCross) isInside = !isInside;
  }
  return isInside;
}

export function round(n: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(n * factor) / factor;
}
