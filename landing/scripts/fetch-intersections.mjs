// Data © OpenStreetMap contributors, ODbL
//
// One-off: fetches named-street intersections around the service area from
// Overpass and writes src/data/intersections.json (committed with its output).
// The server matches "A and B" queries against it before calling Nominatim.
// Run from landing/: node scripts/fetch-intersections.mjs
// OVERPASS_JSON=<file> reuses a saved Overpass response instead of fetching.

import { readFile, writeFile } from "node:fs/promises";
import { buildIndex, findIntersection } from "../src/server/intersections.ts";

// Service area plus about 1 km, so nearby outside cross streets resolve to "outside".
const BBOX = [47.645, -122.335, 47.685, -122.28];
const ENDPOINT = "https://overpass-api.de/api/interpreter";
const CLUSTER_M = 150;
const REQUIRED = ["NE 45th St and Brooklyn Ave NE", "NE 45th St and 25th Ave NE"];

const query = `[out:json][timeout:90];
way["highway"~"^(trunk|primary|secondary|tertiary|residential|unclassified|living_street)$"]["name"]
  (${BBOX.join(",")});
out body;
>;
out skel qt;`;

function fail(message) {
	console.error(`[fetch-intersections] ${message}`);
	process.exit(1);
}

/** POSTs the query, backing off and retrying while the server is at capacity (502/504/429). */
async function fetchOverpass() {
	let wait = 5_000;
	for (let attempt = 1; attempt <= 5; attempt++) {
		const response = await fetch(ENDPOINT, {
			method: "POST",
			headers: { "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "packet-landing/fetch-intersections" },
			body: new URLSearchParams({ data: query }),
		});
		if (response.ok) return response.json();
		const isBusy = [429, 502, 503, 504].includes(response.status);
		if (!isBusy || attempt === 5) {
			fail(`[fetchOverpass] Overpass request failed — ${response.status} ${response.statusText}`);
		}
		console.log(`Overpass busy (${response.status}), retrying in ${wait / 1000}s`);
		await new Promise((resolve) => setTimeout(resolve, wait));
		wait *= 2;
	}
	fail("[fetchOverpass] unreachable");
}

const M_PER_DEG_LAT = 111_320;
const M_PER_DEG_LNG = M_PER_DEG_LAT * Math.cos((BBOX[0] * Math.PI) / 180);
function metres(a, b) {
	return Math.hypot((a[0] - b[0]) * M_PER_DEG_LAT, (a[1] - b[1]) * M_PER_DEG_LNG);
}

/** Greedy clusters: a point joins the first cluster whose seed is within CLUSTER_M. */
function cluster(points) {
	const clusters = [];
	for (const p of points) {
		const home = clusters.find((c) => metres(c[0], p) <= CLUSTER_M);
		if (home) home.push(p);
		else clusters.push([p]);
	}
	return clusters.map((c) => [c.reduce((s, p) => s + p[0], 0) / c.length, c.reduce((s, p) => s + p[1], 0) / c.length]);
}

const round5 = (n) => Math.round(n * 1e5) / 1e5;

const data = process.env.OVERPASS_JSON
	? JSON.parse(await readFile(process.env.OVERPASS_JSON, "utf8"))
	: await fetchOverpass();
if (data.remark) fail(`Overpass returned a remark — ${data.remark}`);
const ways = data.elements.filter((el) => el.type === "way");
if (ways.length === 0) fail("Overpass returned no ways");

const coords = new Map();
for (const el of data.elements) if (el.type === "node") coords.set(el.id, [el.lat, el.lon]);

/** node id -> distinct way names through it */
const namesAt = new Map();
for (const way of ways) {
	const name = way.tags?.name;
	if (!name) continue;
	for (const id of way.nodes) {
		if (!namesAt.has(id)) namesAt.set(id, new Set());
		namesAt.get(id).add(name);
	}
}

/** "nameA\u0000nameB" (sorted) -> node coordinates */
const byPair = new Map();
for (const [id, names] of namesAt) {
	if (names.size < 2) continue;
	const point = coords.get(id);
	if (!point) continue;
	const sorted = [...names].sort();
	for (let i = 0; i < sorted.length; i++) {
		for (let j = i + 1; j < sorted.length; j++) {
			const key = `${sorted[i]}\u0000${sorted[j]}`;
			if (!byPair.has(key)) byPair.set(key, []);
			byPair.get(key).push(point);
		}
	}
}

// Grade-separated crossings share no node: NE 45th St's viaduct passes over
// 25th Ave NE. People still name them as cross streets, so for name pairs with no
// shared node anywhere, a segment of one crossing a segment of the other counts.
// Segments are bucketed into a coarse grid so only nearby pairs are compared.
const CELL_DEG = 0.002;
const grid = new Map();
for (const way of ways) {
	const name = way.tags?.name;
	if (!name) continue;
	for (let i = 1; i < way.nodes.length; i++) {
		const a = coords.get(way.nodes[i - 1]);
		const b = coords.get(way.nodes[i]);
		if (!a || !b) continue;
		const segment = { name, a, b };
		for (let x = Math.floor(Math.min(a[0], b[0]) / CELL_DEG); x <= Math.floor(Math.max(a[0], b[0]) / CELL_DEG); x++) {
			for (let y = Math.floor(Math.min(a[1], b[1]) / CELL_DEG); y <= Math.floor(Math.max(a[1], b[1]) / CELL_DEG); y++) {
				const cell = `${x},${y}`;
				if (!grid.has(cell)) grid.set(cell, []);
				grid.get(cell).push(segment);
			}
		}
	}
}

/** Crossing point of segments p1-p2 and q1-q2 (lat/lng treated as planar), or null. */
function crossing(p1, p2, q1, q2) {
	const r = [p2[0] - p1[0], p2[1] - p1[1]];
	const s = [q2[0] - q1[0], q2[1] - q1[1]];
	const denom = r[0] * s[1] - r[1] * s[0];
	if (denom === 0) return null;
	const qp = [q1[0] - p1[0], q1[1] - p1[1]];
	const t = (qp[0] * s[1] - qp[1] * s[0]) / denom;
	const u = (qp[0] * r[1] - qp[1] * r[0]) / denom;
	if (t < 0 || t > 1 || u < 0 || u > 1) return null;
	return [p1[0] + t * r[0], p1[1] + t * r[1]];
}

const crossings = new Map();
for (const segments of grid.values()) {
	for (let i = 0; i < segments.length; i++) {
		for (let j = i + 1; j < segments.length; j++) {
			const m = segments[i];
			const n = segments[j];
			if (m.name === n.name) continue;
			const key = [m.name, n.name].sort().join("\u0000");
			if (byPair.has(key)) continue;
			const point = crossing(m.a, m.b, n.a, n.b);
			if (!point) continue;
			if (!crossings.has(key)) crossings.set(key, []);
			crossings.get(key).push(point);
		}
	}
}
for (const [key, found] of crossings) byPair.set(key, found);

const nameIds = new Map();
const nameId = (name) => {
	if (!nameIds.has(name)) nameIds.set(name, nameIds.size);
	return nameIds.get(name);
};
const points = [];
for (const key of [...byPair.keys()].sort()) {
	const [a, b] = key.split("\u0000");
	for (const [lat, lng] of cluster(byPair.get(key))) points.push([nameId(a), nameId(b), round5(lat), round5(lng)]);
}

const output = {
	source: "© OpenStreetMap contributors, ODbL",
	fetched: new Date().toISOString().slice(0, 10),
	bbox: BBOX,
	names: [...nameIds.keys()],
	points,
};

const index = buildIndex(output);
for (const q of REQUIRED) {
	const hit = findIntersection(q, index);
	if (!hit) fail(`Sanity check failed, missing — ${q}`);
	console.log(`found: ${q} -> ${hit.join(", ")}`);
}

const json = JSON.stringify(output);
await writeFile(new URL("../src/data/intersections.json", import.meta.url), json + "\n");
console.log(`names ${output.names.length}, points ${points.length} (${crossings.size} crossing pairs), ${(json.length / 1024).toFixed(1)} KB`);
