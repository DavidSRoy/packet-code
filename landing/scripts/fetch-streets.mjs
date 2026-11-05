// Data © OpenStreetMap contributors, ODbL
//
// One-off: fetches the streets within 2.5 km of U Village from Overpass,
// simplifies them and writes src/data/streets.json (committed with its output).
// Run from landing/: node scripts/fetch-streets.mjs

import { writeFile } from "node:fs/promises";

const U_VILLAGE = [47.6632, -122.299];
const RADIUS_M = 2500;
const TOLERANCE_M = 8;
const ENDPOINT = "https://overpass-api.de/api/interpreter";
// Montlake Blvd NE (SR 513) is tagged trunk, so trunk joins the main set.
const MAIN = new Set(["trunk", "primary", "secondary", "tertiary"]);
const MINOR = new Set(["residential", "unclassified"]);

const query = `[out:json][timeout:60];
way(around:${RADIUS_M},${U_VILLAGE[0]},${U_VILLAGE[1]})
  ["highway"~"^(trunk|primary|secondary|tertiary|residential|unclassified)$"];
out geom;`;

const M_PER_DEG_LAT = 111_320;
const M_PER_DEG_LNG = M_PER_DEG_LAT * Math.cos((U_VILLAGE[0] * Math.PI) / 180);

/** Lat/lng to local metres (east, north) around U Village. */
function toMetres([lat, lng]) {
	return [(lng - U_VILLAGE[1]) * M_PER_DEG_LNG, (lat - U_VILLAGE[0]) * M_PER_DEG_LAT];
}

function segmentDistance(p, a, b) {
	const dx = b[0] - a[0];
	const dy = b[1] - a[1];
	const len2 = dx * dx + dy * dy;
	const k = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
	return Math.hypot(p[0] - (a[0] + k * dx), p[1] - (a[1] + k * dy));
}

/** Douglas–Peucker on lat/lng points, measured in local metres. */
function simplify(points) {
	if (points.length < 3) return points;
	const m = points.map(toMetres);
	const keep = new Uint8Array(points.length);
	keep[0] = 1;
	keep[points.length - 1] = 1;
	const stack = [[0, points.length - 1]];
	while (stack.length) {
		const [first, last] = stack.pop();
		let maxD = 0;
		let index = -1;
		for (let i = first + 1; i < last; i++) {
			const d = segmentDistance(m[i], m[first], m[last]);
			if (d > maxD) {
				maxD = d;
				index = i;
			}
		}
		if (maxD > TOLERANCE_M && index > 0) {
			keep[index] = 1;
			stack.push([first, index], [index, last]);
		}
	}
	return points.filter((_, i) => keep[i]);
}

const round5 = (n) => Math.round(n * 1e5) / 1e5;

/** POSTs the query, backing off and retrying while the server is at capacity (502/504/429). */
async function fetchOverpass() {
	let wait = 5_000;
	for (let attempt = 1; attempt <= 5; attempt++) {
		const response = await fetch(ENDPOINT, {
			method: "POST",
			headers: { "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "packet-landing/fetch-streets" },
			body: new URLSearchParams({ data: query }),
		});
		if (response.ok) return response.json();
		const isBusy = [429, 502, 503, 504].includes(response.status);
		if (!isBusy || attempt === 5) {
			throw new Error(`[fetch-streets:fetchOverpass] Overpass request failed — ${response.status} ${response.statusText}`);
		}
		console.log(`Overpass busy (${response.status}), retrying in ${wait / 1000}s`);
		await new Promise((resolve) => setTimeout(resolve, wait));
		wait *= 2;
	}
	throw new Error("[fetch-streets:fetchOverpass] unreachable");
}

const data = await fetchOverpass();
// Overpass reports timeouts and memory limits as a `remark` on a 200 response.
if (data.remark) throw new Error(`[fetch-streets:main] Overpass returned a remark — ${data.remark}`);
if (!data.elements?.some((el) => el.type === "way")) throw new Error("[fetch-streets:main] Overpass returned no ways");

const main = [];
const minor = [];
for (const el of data.elements) {
	if (el.type !== "way" || !el.geometry) continue;
	const kind = el.tags?.highway;
	const bucket = MAIN.has(kind) ? main : MINOR.has(kind) ? minor : null;
	if (!bucket) continue;
	const line = simplify(el.geometry.map((g) => [g.lat, g.lon])).map(([lat, lng]) => [round5(lat), round5(lng)]);
	if (line.length >= 2) bucket.push(line);
}

const names = new Set(data.elements.filter((el) => MAIN.has(el.tags?.highway)).map((el) => el.tags?.name));
for (const name of ["Montlake Boulevard Northeast", "Northeast 45th Street", "25th Avenue Northeast"]) {
	console.log(`${names.has(name) ? "found" : "MISSING"}: ${name}`);
}

const json = JSON.stringify({ main, minor });
await writeFile(new URL("../src/data/streets.json", import.meta.url), json + "\n");
console.log(`main ${main.length}, minor ${minor.length}, ${(json.length / 1024).toFixed(1)} KB`);
