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
	/** Holds the three step bullets (`[data-bullet]`); the route runs through their centers. */
	stepsRef: RefObject<HTMLElement | null>;
}

export function TripCanvas(props: Props) {
	const { stepsRef } = props;
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
			if (xs.length !== 3 || xs[2] - xs[0] < w * 0.3) xs = [w * 0.08, w * 0.5, w * 0.92];
			const s = Math.max(8, Math.min(14, w / 80));
			const lw = Math.max(2, s * 0.22);
			const ys = [h * 0.72, h * 0.5, h * 0.28];
			const m01 = (xs[0] + xs[1]) / 2;
			const m12 = (xs[1] + xs[2]) / 2;
			const legs: Pt[][] = [
				[[xs[0], ys[0]], [m01, ys[0]], [m01, ys[1]], [xs[1], ys[1]]],
				[[xs[1], ys[1]], [m12, ys[1]], [m12, ys[2]], [xs[2], ys[2]]],
			];
			ctx.fillStyle = INK.black;
			dots(ctx, [...pairs(legs[0]), ...pairs(legs[1])], 1.5);
			const p = ease(clamp01(progressRef.current));
			const first = walk(legs[0], clamp01(p * 2));
			const second = walk(legs[1], clamp01(p * 2 - 1));
			ctx.fillStyle = INK.mustard;
			dots(ctx, p <= 0.5 ? first.trail : [...first.trail, ...second.trail], 3.2);
			const [ix, iy] = p <= 0.5 ? first.p : second.p;
			drawMarks(ctx, ix, iy, s, p >= 0.999 ? 0.7 : 1, lw, true);
		}
		const handle = mountCanvas(canvas, draw, { isAnimated: false });
		handleRef.current = handle;
		return () => {
			handle.destroy();
			handleRef.current = null;
		};
	}, [stepsRef]);

	useEffect(() => {
		progressRef.current = props.progress;
		handleRef.current?.paint();
	}, [props.progress]);

	return (
		<canvas
			ref={canvasRef}
			role="img"
			aria-label="The Packet icon travels along a dotted route past the three steps"
			className="absolute inset-0 block h-full w-full"
		/>
	);
}
