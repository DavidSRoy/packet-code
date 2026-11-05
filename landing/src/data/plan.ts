import { SERVICE_AREA, U_VILLAGE } from "@/config/service-area";
import type { LatLng } from "@/lib/geo";
import { areaPath, places, projectPlan, streetsPath, type Place, type Pt } from "@/lib/plan";
import streetsJson from "./streets.json";

const toLine = (line: readonly (readonly number[])[]): LatLng[] => line.map((p): LatLng => [p[0], p[1]]);

export interface Plan {
	main: string;
	minor: string;
	area: string;
	hub: Pt;
}

/** Built once at module load from the baked streets and the service-area polygon. */
export const PLAN: Plan = {
	main: streetsPath(streetsJson.main.map(toLine)),
	minor: streetsPath(streetsJson.minor.map(toLine)),
	area: areaPath(SERVICE_AREA),
	hub: projectPlan(U_VILLAGE),
};

/** Named places on the plan. Steps 1 to 5 are inside the first area and name themselves in that order. */
export const PLACES: readonly Place[] = places([
	{ name: "University Village", at: [47.6648, -122.2992], step: 1 },
	{ name: "U District", at: [47.6595, -122.3135], step: 2 },
	{ name: "UW north campus", at: [47.6598, -122.3045], step: 3, anchor: "start" },
	{ name: "Bryant", at: [47.6708, -122.2875], step: 4 },
	{ name: "Mercer Court", at: [47.6549, -122.3138], step: 5 },
	{ name: "Ravenna", at: [47.6745, -122.3085], step: 0 },
	{ name: "Laurelhurst", at: [47.6585, -122.277], step: 0, anchor: "end" },
]);
