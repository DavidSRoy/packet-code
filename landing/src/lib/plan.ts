import type { LatLng } from "./geo.ts";

/** The plan of the first area: a flat projection of the streets around U Village, in a 640 by 460 box. */
export const PLAN_W = 640;
export const PLAN_H = 460;

const LAT0 = 47.6635;
const LNG0 = -122.306;
/** Degrees of longitude across the plan's width. */
const DEG_W = 0.062;
const COS = Math.cos((LAT0 * Math.PI) / 180);
const K = PLAN_W / (DEG_W * COS);

export type Pt = readonly [x: number, y: number];

export function projectPlan(p: LatLng): Pt {
	return [(p[1] - LNG0) * COS * K + PLAN_W / 2, -(p[0] - LAT0) * K + PLAN_H / 2];
}

function isInView([x, y]: Pt): boolean {
	return x > -20 && x < PLAN_W + 20 && y > -20 && y < PLAN_H + 20;
}

const r1 = (n: number): number => Math.round(n * 10) / 10;

/** One SVG path through every polyline that touches the plan. */
export function streetsPath(lines: readonly (readonly LatLng[])[]): string {
	const parts: string[] = [];
	for (const line of lines) {
		const pts = line.map(projectPlan);
		if (!pts.some(isInView)) continue;
		parts.push("M" + pts.map(([x, y]) => `${r1(x)} ${r1(y)}`).join("L"));
	}
	return parts.join("");
}

/** The closed boundary. */
export function areaPath(area: readonly LatLng[]): string {
	return "M" + area.map(projectPlan).map(([x, y]) => `${r1(x)} ${r1(y)}`).join("L") + "Z";
}

export type Anchor = "start" | "middle" | "end";

export interface Place {
	name: string;
	x: number;
	y: number;
	/** Order in which the first-area places name themselves; 0 for places outside it. */
	step: number;
	/** Which edge of the label sits on the point. */
	anchor: Anchor;
}

export interface PlaceSource {
	name: string;
	at: LatLng;
	step: number;
	anchor?: Anchor;
}

export function places(sources: readonly PlaceSource[]): Place[] {
	return sources.map((s) => {
		const [x, y] = projectPlan(s.at);
		return { name: s.name, x: r1(x), y: r1(y), step: s.step, anchor: s.anchor ?? "middle" };
	});
}
