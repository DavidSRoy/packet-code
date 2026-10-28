import { useEffect, useRef, type RefObject } from "react";
import type { LatLng } from "@/lib/geo";
import { project, toSphere, type SphereView } from "@/lib/canvas/sphere";

export type Rotation = readonly [yaw: number, pitch: number];

/** Where on screen a checked point should land: beside the copy, upper left of the globe. */
export interface Anchor {
	x: number;
	y: number;
}

export interface GlobeAimState {
	/** The checked point as sphere [lon, lat], or null to drift. */
	target: readonly [number, number] | null;
	from: Rotation;
	/** Solved lazily on the first frame after a check, once the view is known. */
	to: Rotation | null;
	t0: number;
	rot: Rotation;
	lastT: number;
}

const TURN_S = 1.4;
const MARKS_DELAY_S = 1.0;
const MARKS_S = 0.8;
const DRIFT_SPEED = 0.03;
const PITCH = 0.42;
/**
 * The mockup drifts yaw without bound over an endless procedural grid. The real
 * street map is a finite disc, so the yaw swings back and forth instead
 * (starting at the mockup's speed) to keep U Village in view.
 */
const DRIFT_AMPLITUDE = 0.35;

const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));
const ease = (x: number): number => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const lerp = (a: number, b: number, x: number): number => a + (b - a) * x;

function driftAt(t: number): Rotation {
	return [DRIFT_AMPLITUDE * Math.sin((t * DRIFT_SPEED) / DRIFT_AMPLITUDE), PITCH];
}

/** Picks the rotation that lands the target nearest the anchor, on the near side, by a coarse search. */
function aim(view: Omit<SphereView, "rot">, target: readonly [number, number], anchor: Anchor): Rotation | null {
	const [lon, lat] = target;
	let best: Rotation | null = null;
	let bestD = Infinity;
	for (let i = -30; i <= 30; i++) {
		for (let j = -30; j <= 30; j++) {
			const rot: Rotation = [lon + i * 0.04, j * 0.04];
			const [x, y, z] = project({ ...view, rot }, lon, lat);
			if (z <= 0.2) continue;
			const d = Math.hypot(x - anchor.x, y - anchor.y);
			if (d < bestD) {
				bestD = d;
				best = rot;
			}
		}
	}
	return best;
}

/** The globe's rotation at time t: drift, or the turn toward the checked point. */
export function globeRotation(
	state: GlobeAimState,
	t: number,
	view: Omit<SphereView, "rot">,
	anchor: Anchor,
	isAnimated: boolean,
): Rotation {
	state.lastT = t;
	let rot = driftAt(t);
	if (state.target) {
		state.to ??= aim(view, state.target, anchor);
		if (state.to) {
			const k = isAnimated ? ease(clamp01((t - state.t0) / TURN_S)) : 1;
			rot = [lerp(state.from[0], state.to[0], k), lerp(state.from[1], state.to[1], k)];
		}
	}
	state.rot = rot;
	return rot;
}

/** How far the corner marks have closed on the target, 0 to 1. */
export function marksProgress(state: GlobeAimState, t: number, isAnimated: boolean): number {
	if (!state.target || !state.to) return 0;
	return isAnimated ? ease(clamp01((t - state.t0 - MARKS_DELAY_S) / MARKS_S)) : 1;
}

/** Holds the globe's turn state across frames; a new target starts a turn from wherever the globe is. */
export function useGlobeAim(target: LatLng | null): RefObject<GlobeAimState> {
	const state = useRef<GlobeAimState>({ target: null, from: driftAt(0), to: null, t0: 0, rot: driftAt(0), lastT: 0 });
	const lat = target ? target[0] : null;
	const lng = target ? target[1] : null;
	useEffect(() => {
		const s = state.current;
		s.from = s.rot;
		s.t0 = s.lastT;
		s.to = null;
		s.target = lat === null || lng === null ? null : toSphere([lat, lng]);
	}, [lat, lng]);
	return state;
}
