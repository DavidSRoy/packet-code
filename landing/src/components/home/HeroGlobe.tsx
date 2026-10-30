"use client";

import { useEffect, useRef } from "react";
import { SERVICE_AREA } from "@/config/service-area";
import streetsJson from "@/data/streets.json";
import type { LatLng } from "@/lib/geo";
import { mountCanvas, type CanvasHandle } from "@/lib/canvas/loop";
import { drawMarks } from "@/lib/canvas/marks";
import { drawSphere, project, type SphereView, type Streets } from "@/lib/canvas/sphere";
import { globeRotation, marksProgress, useGlobeAim, type Anchor } from "./useGlobeAim";

const toLine = (line: readonly (readonly number[])[]): LatLng[] => line.map((p): LatLng => [p[0], p[1]]);

const STREETS: Streets = { main: streetsJson.main.map(toLine), minor: streetsJson.minor.map(toLine) };

/** The copy column the globe keeps clear of. Task 6's copy must carry this attribute. */
const COPY_SELECTOR = "[data-hero-copy]";
const COPY_MAX_W = 440;

interface Props {
	/** The checked address. The globe turns to it and closes the corner marks on it; null drifts. */
	target: LatLng | null;
}

/** Globe placement from the mockup: low and right, bleeding off the edge. */
function heroView(w: number, h: number): Omit<SphereView, "rot"> {
	const isNarrow = w < 700;
	return {
		cx: isNarrow ? w * 0.78 : w * 0.88,
		cy: isNarrow ? h * 0.95 : h * 0.86,
		R: isNarrow ? w * 0.95 : Math.max(w, h) * 0.6,
		roll: -0.5,
		step: Math.max(5, Math.min(8, w / 190)),
	};
}

interface Layout {
	/** Art is clipped to x >= clipX so nothing runs under the copy. */
	clipX: number;
	anchor: Anchor;
}

function measure(canvas: HTMLCanvasElement, w: number, h: number): Layout {
	const r = canvas.getBoundingClientRect();
	const copy = canvas.parentElement?.querySelector(COPY_SELECTOR);
	const c = copy ? copy.getBoundingClientRect() : null;
	const isOverlapping = c !== null && c.top < r.bottom && c.bottom > r.top && c.left < r.right;
	const isNarrow = r.width < 700;
	// The copy box is content-box: left padding, then up to COPY_MAX_W of content.
	const padL = copy ? parseFloat(getComputedStyle(copy).paddingLeft) || 0 : 0;
	const padR = copy ? parseFloat(getComputedStyle(copy).paddingRight) || 0 : 0;
	return {
		clipX: c && isOverlapping ? c.left - r.left + padL + Math.min(c.width - padL - padR, COPY_MAX_W) + 40 : 0,
		anchor: {
			x: isNarrow || !c ? w * 0.5 : Math.max(c.right - r.left + 120, w * 0.55),
			y: h * (isNarrow ? 0.45 : 0.42),
		},
	};
}

export function HeroGlobe(props: Props) {
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const handleRef = useRef<CanvasHandle | null>(null);
	const aimRef = useGlobeAim(props.target);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		const isAnimated = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		const handle = mountCanvas(
			canvas,
			(ctx, w, h, t) => {
				const aim = aimRef.current;
				const layout = measure(canvas, w, h);
				const base = heroView(w, h);
				const view: SphereView = { ...base, rot: globeRotation(aim, t, base, layout.anchor, isAnimated) };
				ctx.save();
				ctx.beginPath();
				ctx.rect(layout.clipX, 0, w - layout.clipX, h);
				ctx.clip();
				drawSphere(ctx, w, h, view, STREETS, SERVICE_AREA);
				const p = marksProgress(aim, t, isAnimated);
				if (aim.target && p > 0) {
					const [x, y, z] = project(view, aim.target[0], aim.target[1]);
					if (z > 0) {
						ctx.globalAlpha = p;
						drawMarks(ctx, x, y, Math.max(8, w / 110), 3 - 2 * p, 2.5, false);
						ctx.globalAlpha = 1;
					}
				}
				ctx.restore();
			},
			{ isAnimated },
		);
		handleRef.current = handle;
		return () => {
			handle.destroy();
			handleRef.current = null;
		};
	}, [aimRef]);

	// Repaint on a new target so a still (reduced-motion) globe shows the turn's final state.
	useEffect(() => {
		handleRef.current?.paint();
	}, [props.target]);

	return (
		<canvas
			ref={canvasRef}
			role="img"
			aria-label="Dotted street grid around University Village on a slowly turning globe"
			className="absolute inset-0 block h-full w-full max-[760px]:relative max-[760px]:inset-auto max-[760px]:order-first max-[760px]:h-[300px]"
		/>
	);
}
