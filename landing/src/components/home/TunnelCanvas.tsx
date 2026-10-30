"use client";

import { useEffect, useRef } from "react";
import { mountCanvas } from "@/lib/canvas/loop";
import { INK } from "@/lib/canvas/sphere";

/** Dotted corner marks rush toward a vanishing point. Nothing sits at the center. */
function drawTunnel(ctx: CanvasRenderingContext2D, w: number, h: number, t: number): void {
	const vx = w * 0.45;
	const vy = h * 0.5;
	const tile = Math.max(56, Math.min(88, w / 8));
	const D0 = tile * 0.75;
	const q = 1.42;
	const Dmax = Math.hypot(w, h);
	const f = (t * 0.2) % 1;
	ctx.fillStyle = INK.black;
	for (let i = 0; ; i++) {
		const D = D0 * Math.pow(q, i + f);
		if (D > Dmax) break;
		const rot = 0.025 * (i + f);
		const cr = Math.cos(rot);
		const sr = Math.sin(rot);
		const r = Math.max(0.8, Math.min(5, D * 0.011));
		const sp = Math.max(3, r * 2.7);
		const off = D * 0.075;
		const len = D * 0.2;
		ctx.globalAlpha = Math.min(1, (D - D0) / (D0 * 0.8));
		for (const sx of [-1, 1]) {
			for (const sy of [-1, 1]) {
				for (let a = 0; a <= len; a += sp) {
					const pts: [number, number][] = [
						[sx * (D + off + a), sy * D],
						[sx * D, sy * (D + off + a)],
					];
					for (const [x, y] of pts) {
						const X = vx + x * cr - y * sr;
						const Y = vy + x * sr + y * cr;
						if (X < -10 || X > w + 10 || Y < -10 || Y > h + 10) continue;
						ctx.beginPath();
						ctx.arc(X, Y, r, 0, Math.PI * 2);
						ctx.fill();
					}
				}
			}
		}
	}
	ctx.globalAlpha = 1;
}

export function TunnelCanvas() {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const isAnimated = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		const handle = mountCanvas(canvas, drawTunnel, { isAnimated });
		return () => handle.destroy();
	}, []);

	return (
		<canvas
			ref={canvasRef}
			role="img"
			aria-label="Dotted corner marks rush toward a vanishing point"
			className="absolute inset-0 block h-full w-full"
		/>
	);
}
