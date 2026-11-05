"use client";

import { useEffect, useRef, type RefObject } from "react";
import { mountCanvas, type CanvasHandle } from "@/lib/canvas/loop";
import { drawMarks } from "@/lib/canvas/marks";
import { INK } from "@/lib/canvas/sphere";

type Pt = readonly [number, number];
type Seg = readonly [Pt, Pt];

function clamp01(x: number): number {
	return Math.max(0, Math.min(1, x));
}

function ease(x: number): number {
	return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

function pairs(leg: readonly Pt[]): Seg[] {
	return leg.slice(1).map((b, i) => [leg[i], b] as const);
}

function dots(ctx: CanvasRenderingContext2D, segs: readonly Seg[], r: number): void {
	for (const [[x1, y1], [x2, y2]] of segs) {
		const n = Math.max(1, Math.round(Math.hypot(x2 - x1, y2 - y1) / 8));
		for (let i = 0; i <= n; i++) {
			ctx.beginPath();
			ctx.arc(x1 + ((x2 - x1) * i) / n, y1 + ((y2 - y1) * i) / n, r, 0, Math.PI * 2);
			ctx.fill();
		}
	}
}

/** Position after travelling fraction f of a leg, and the segments covered so far. */
function walk(leg: readonly Pt[], f: number): { p: Pt; trail: Seg[] } {
	const segs = pairs(leg);
	const lens = segs.map(([a, b]) => Math.hypot(b[0] - a[0], b[1] - a[1]));
	let d = f * lens.reduce((a, b) => a + b, 0);
	const trail: Seg[] = [];
	for (let i = 0; i < segs.length; i++) {
		const [a, b] = segs[i];
		if (d <= lens[i]) {
			const g = lens[i] ? d / lens[i] : 0;
			const p: Pt = [a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g];
			trail.push([a, p]);
			return { p, trail };
		}
		trail.push([a, b]);
		d -= lens[i];
	}
	return { p: leg[leg.length - 1], trail };
}

interface Props {
	/** 0 to 1: how far the icon has travelled. */
	progress: number;
	/** Holds the step bullets (`[data-bullet]`); the route runs through their centers, one stop each. */
	stepsRef: RefObject<HTMLElement | null>;
	/** How many stops to draw when the bullets cannot be measured. */
	stopCount: number;
}

export function TripCanvas(props: Props) {
	const { stepsRef, stopCount } = props;
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const handleRef = useRef<CanvasHandle | null>(null);
	const progressRef = useRef(0);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		function draw(ctx: CanvasRenderingContext2D, w: number, h: number): void {
			if (!canvas) return;
			const r = canvas.getBoundingClientRect();
			const bullets = stepsRef.current?.querySelectorAll("[data-bullet]") ?? [];
			let xs = Array.from(bullets, (b) => {
				const q = b.getBoundingClientRect();
				return q.left - r.left + q.width / 2;
			});
			const n = Math.max(2, xs.length || stopCount);
			// Stacked layouts put bullets in columns: then the route takes evenly spaced stops instead.
			const isOrdered = xs.every((x, i) => i === 0 || x > xs[i - 1] + 24);
			if (xs.length !== n || !isOrdered || xs[n - 1] - xs[0] < w * 0.3) {
				xs = Array.from({ length: n }, (_, i) => w * (0.08 + (0.84 * i) / (n - 1)));
			}
			const s = Math.max(8, Math.min(14, w / 80));
			const lw = Math.max(2, s * 0.22);
			// Each stop sits a little higher than the last, so the route climbs across the section.
			const ys = xs.map((_, i) => h * (0.78 - (0.56 * i) / (n - 1)));
			const legs: Pt[][] = [];
			for (let i = 0; i < n - 1; i++) {
				const mid = (xs[i] + xs[i + 1]) / 2;
				legs.push([
					[xs[i], ys[i]],
					[mid, ys[i]],
					[mid, ys[i + 1]],
					[xs[i + 1], ys[i + 1]],
				]);
			}
			ctx.fillStyle = INK.black;
			dots(ctx, legs.flatMap(pairs), 1.5);
			const p = ease(clamp01(progressRef.current));
			const scaled = p * (n - 1);
			const index = Math.min(n - 2, Math.floor(scaled));
			const local = clamp01(scaled - index);
			const current = walk(legs[index], local);
			const trail = [...legs.slice(0, index).flatMap(pairs), ...current.trail];
			ctx.fillStyle = INK.mustard;
			dots(ctx, trail, 3.2);
			const [ix, iy] = current.p;
			drawMarks(ctx, ix, iy, s, p >= 0.999 ? 0.7 : 1, lw, true);
		}
		const handle = mountCanvas(canvas, draw, { isAnimated: false });
		handleRef.current = handle;
		return () => {
			handle.destroy();
			handleRef.current = null;
		};
	}, [stepsRef, stopCount]);

	useEffect(() => {
		progressRef.current = props.progress;
		handleRef.current?.paint();
	}, [props.progress]);

	return (
		<canvas
			ref={canvasRef}
			role="img"
			aria-label="The Packet icon travels along a dotted route past the steps"
			className="absolute inset-0 block h-full w-full"
		/>
	);
}
