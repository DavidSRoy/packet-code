import data from "../data/intersections.json" with { type: "json" };
import { buildIndex, isIntersectionData, type IntersectionIndex } from "./intersections.ts";

function load(): IntersectionIndex {
  if (!isIntersectionData(data)) throw new Error("[Intersections:load] intersections.json has an unexpected shape");
  return buildIndex(data);
}

/** Built once per isolate. Server-only: imported by the API routes, never by a client component. */
export const INTERSECTIONS: IntersectionIndex = load();
