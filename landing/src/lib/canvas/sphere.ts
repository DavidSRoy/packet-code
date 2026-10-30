import { U_VILLAGE } from "@/config/service-area";
import type { LatLng } from "@/lib/geo";

interface Inks {
	readonly red: string;
	readonly mustard: string;
	readonly black: string;
}

export const INK: Inks = { red: "#B4432F", mustard: "#D3A13F", black: "#111111" };

export interface Streets {
	main: readonly (readonly LatLng[])[];
	minor: readonly (readonly LatLng[])[];
}

/** Where the globe sits on screen and how it is turned. rot is [yaw, pitch]. */
export interface SphereView {
	cx: number;
	cy: number;
	R: number;
	roll: number;
	step: number;
	rot: readonly [number, number];
}

/** Sphere radians per metre on the ground. Sized so U Village, NE 45th St and the Montlake curve share the hero. */
const RAD_PER_M = 0.0004;
/**
 * Where U Village sits on the sphere, as [lon, lat]. Chosen so that at the
 * drift's resting rotation [0, 0.42] U Village lands in the hero's visible
 * upper-left of the globe, right of the copy (about x 1000, y 270 at 1440).
 */
const MAP_CENTRE: readonly [lon: number, lat: number] = [-0.02, -1.1];
const C_LON = Math.cos(MAP_CENTRE[0]);
const S_LON = Math.sin(MAP_CENTRE[0]);
const C_LAT = Math.cos(MAP_CENTRE[1]);
const S_LAT = Math.sin(MAP_CENTRE[1]);
const M_PER_DEG_LAT = 111_320;
const M_PER_DEG_LNG = M_PER_DEG_LAT * Math.cos((U_VILLAGE[0] * Math.PI) / 180);

/**
 * The street map is laid on the sphere by an azimuthal equidistant projection
 * centred on U Village: distance from U Village on the ground is arc length on
 * the sphere, so the map stays true near the centre and never folds at a pole.
 * Plane (u, v) is (east, south) in sphere radians. The map is built around
 * sphere (0, 0) and then turned so its centre sits at MAP_CENTRE.
 */
function toPlane(p: LatLng): [u: number, v: number] {
	return [(p[1] - U_VILLAGE[1]) * M_PER_DEG_LNG * RAD_PER_M, -(p[0] - U_VILLAGE[0]) * M_PER_DEG_LAT * RAD_PER_M];
}

/** Lat/lng on the ground to sphere [lon, lat] (radians) around U Village. */
export function toSphere(p: LatLng): [lon: number, lat: number] {
	const [u, v] = toPlane(p);
	const c = Math.hypot(u, v);
	const s = c === 0 ? 1 : Math.sin(c) / c;
	const x = u * s;
	const y = v * s;
	const z = Math.cos(c);
	// pitch to the centre's lat, then yaw to its lon
	const y1 = y * C_LAT + z * S_LAT;
	const z1 = -y * S_LAT + z * C_LAT;
	const x2 = x * C_LON + z1 * S_LON;
	const z2 = -x * S_LON + z1 * C_LON;
	return [Math.atan2(x2, z2), Math.asin(Math.max(-1, Math.min(1, y1)))];
}

/** Texture point to screen, the inverse of drawSphere's rotation; z < 0 is the far side. */
export function project(o: SphereView, lon: number, lat: number): [x: number, y: number, z: number] {
	const x2 = Math.cos(lat) * Math.sin(lon);
	const y1 = Math.sin(lat);
	const z2 = Math.cos(lat) * Math.cos(lon);
	const [ay, ax] = o.rot;
	const cY = Math.cos(ay);
	const sY = Math.sin(ay);
	const cX = Math.cos(ax);
	const sX = Math.sin(ax);
	const xr = x2 * cY - z2 * sY;
	const z1 = x2 * sY + z2 * cY;
	const yr = y1 * cX + z1 * sX;
	const cg = Math.cos(o.roll);
	const sg = Math.sin(o.roll);
	return [o.cx + (xr * cg - yr * sg) * o.R, o.cy + (xr * sg + yr * cg) * o.R, -y1 * sX + z1 * cX];
}

/** Streets rasterised once into the (u, v) plane: 0 none, 1 minor, 2 main. */
interface StreetTexture {
	size: number;
	extent: number;
	cells: Uint8Array;
}

const TEXTURE_SIZE = 1024;
/** Full stroke widths in sphere radians, from the mockup's grid thresholds. */
const MAIN_WIDTH = 0.0145;
const MINOR_WIDTH = 0.008;

const textures = new WeakMap<Streets, StreetTexture>();

function buildTexture(streets: Streets): StreetTexture | null {
	let extent = 0;
	for (const line of [...streets.main, ...streets.minor]) {
		for (const p of line) {
			const [u, v] = toPlane(p);
			extent = Math.max(extent, Math.abs(u), Math.abs(v));
		}
	}
	extent += MAIN_WIDTH;
	const size = TEXTURE_SIZE;
	const canvas = document.createElement("canvas");
	canvas.width = size;
	canvas.height = size;
	const ctx = canvas.getContext("2d", { willReadFrequently: true });
	if (!ctx) {
		console.error("[sphere:buildTexture] 2D context unavailable — {}");
		return null;
	}
	const scale = size / (2 * extent);
	ctx.lineCap = "round";
	ctx.lineJoin = "round";
	const stroke = (lines: Streets["main"], color: string, width: number): void => {
		ctx.strokeStyle = color;
		ctx.lineWidth = width * scale;
		ctx.beginPath();
		for (const line of lines) {
			line.forEach((p, i) => {
				const [u, v] = toPlane(p);
				const x = (u + extent) * scale;
				const y = (v + extent) * scale;
				if (i === 0) ctx.moveTo(x, y);
				else ctx.lineTo(x, y);
			});
		}
		ctx.stroke();
	};
	stroke(streets.minor, "rgb(0,255,0)", MINOR_WIDTH);
	stroke(streets.main, "rgb(255,0,0)", MAIN_WIDTH);
	const data = ctx.getImageData(0, 0, size, size).data;
	const cells = new Uint8Array(size * size);
	for (let i = 0; i < cells.length; i++) {
		cells[i] = data[i * 4] > 127 ? 2 : data[i * 4 + 1] > 127 ? 1 : 0;
	}
	return { size, extent, cells };
}

function textureFor(streets: Streets): StreetTexture | null {
	const cached = textures.get(streets);
	if (cached) return cached;
	const built = buildTexture(streets);
	if (built) textures.set(streets, built);
	return built;
}

/** Dot radius (as a share of the step) and opacity per street class. Main reads darker than minor. */
interface Dot {
	v: number;
	a: number;
}

const DOT: readonly (Dot | null)[] = [null, { v: 0.38, a: 0.55 }, { v: 0.75, a: 1 }];

/** Points along each edge so the outline follows the sphere instead of cutting chords. */
const OUTLINE_STEPS = 20;

/**
 * Halftone sphere: one dot per screen cell where the cell, turned back onto the
 * sphere, lands on a street. Then the service area as a dotted outline.
 */
export function drawSphere(
	ctx: CanvasRenderingContext2D,
	w: number,
	h: number,
	o: SphereView,
	streets: Streets,
	outline: readonly LatLng[],
): void {
	const texture = textureFor(streets);
	if (!texture) return;
	const { cx, cy, R, step } = o;
	const [ay, ax] = o.rot;
	const cg = Math.cos(o.roll);
	const sg = Math.sin(o.roll);
	const cY = Math.cos(ay);
	const sY = Math.sin(ay);
	const cX = Math.cos(ax);
	const sX = Math.sin(ax);
	const { size, extent, cells } = texture;
	const toCell = size / (2 * extent);
	ctx.fillStyle = INK.black;
	for (let py = step / 2; py < h; py += step) {
		for (let px = step / 2; px < w; px += step) {
			const x = (px - cx) / R;
			const y = (py - cy) / R;
			const d2 = x * x + y * y;
			if (d2 >= 1) continue;
			const z = Math.sqrt(1 - d2);
			// roll the view so the streets run at an angle
			const xr = x * cg + y * sg;
			const yr = -x * sg + y * cg;
			const y1 = yr * cX - z * sX;
			const z1 = yr * sX + z * cX;
			const x2 = xr * cY + z1 * sY;
			const z2 = -xr * sY + z1 * cY;
			// undo the map's turn to MAP_CENTRE, then sphere point to the map plane
			const mx = x2 * C_LON - z2 * S_LON;
			const mz1 = x2 * S_LON + z2 * C_LON;
			const my = y1 * C_LAT - mz1 * S_LAT;
			const mz = y1 * S_LAT + mz1 * C_LAT;
			const c = Math.acos(Math.max(-1, Math.min(1, mz)));
			const s = Math.hypot(mx, my);
			const k = s > 0 ? c / s : 0;
			const col = Math.floor((mx * k + extent) * toCell);
			const row = Math.floor((my * k + extent) * toCell);
			if (col < 0 || row < 0 || col >= size || row >= size) continue;
			const dot = DOT[cells[row * size + col]];
			if (!dot) continue;
			const r = dot.v * step * 0.48;
			ctx.globalAlpha = (0.35 + 0.65 * z) * dot.a;
			ctx.beginPath();
			// radial axis foreshortened by depth: dots stretch along the rim
			ctx.ellipse(px, py, Math.max(0.6, r * Math.max(0.22, z)), r, Math.atan2(y, x), 0, Math.PI * 2);
			ctx.fill();
		}
	}
	ctx.globalAlpha = 1;
	drawOutline(ctx, o, outline);
}

function drawOutline(ctx: CanvasRenderingContext2D, o: SphereView, outline: readonly LatLng[]): void {
	if (outline.length < 2) return;
	ctx.save();
	ctx.strokeStyle = INK.black;
	ctx.globalAlpha = 0.6;
	ctx.lineWidth = 2.5;
	ctx.lineCap = "round";
	ctx.setLineDash([0, 7]);
	ctx.beginPath();
	let isDrawing = false;
	for (let i = 0; i < outline.length; i++) {
		const a = outline[i];
		const b = outline[(i + 1) % outline.length];
		for (let j = 0; j < OUTLINE_STEPS; j++) {
			const f = j / OUTLINE_STEPS;
			const [lon, lat] = toSphere([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]);
			const [x, y, z] = project(o, lon, lat);
			if (z <= 0) {
				isDrawing = false;
			} else if (isDrawing) {
				ctx.lineTo(x, y);
			} else {
				ctx.moveTo(x, y);
				isDrawing = true;
			}
		}
	}
	const [lon, lat] = toSphere(outline[0]);
	const [x, y, z] = project(o, lon, lat);
	if (isDrawing && z > 0) ctx.lineTo(x, y);
	ctx.stroke();
	ctx.restore();
}
