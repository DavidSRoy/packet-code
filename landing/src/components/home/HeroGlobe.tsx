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

/** Width over which the art fades out before the copy column. */
const FADE_PX = 160;

/** Globe placement: right of the copy, small enough that its rim shows, bleeding off the right edge. */
function heroView(w: number, h: number): Omit<SphereView, "rot"> {
	// Matches the stacked layout in Hero.tsx: under 900px the globe sits above the copy, centred.
	const isNarrow = w < 900;
	const R = isNarrow ? h * 0.46 : Math.min(h * 0.47, w * 0.36);
	return {
		cx: isNarrow ? w * 0.5 : w - R * 0.7,
		cy: h * 0.5,
		R,
		roll: -0.5,
		step: Math.max(4, Math.min(8, R / 60)),
	};
}

interface Layout {
	/** Art is clipped to x >= clipX so nothing runs under the copy. */
	clipX: number;
	anchor: Anchor;
}

function measure(canvas: HTMLCanvasElement, view: Omit<SphereView, "rot">): Layout {
	const r = canvas.getBoundingClientRect();
	const copy = canvas.parentElement?.querySelector(COPY_SELECTOR);
	const c = copy ? copy.getBoundingClientRect() : null;
	const isOverlapping = c !== null && c.top < r.bottom && c.bottom > r.top && c.left < r.right;
	// The copy box is content-box: left padding, then up to COPY_MAX_W of content.
	const padL = copy ? parseFloat(getComputedStyle(copy).paddingLeft) || 0 : 0;
	const padR = copy ? parseFloat(getComputedStyle(copy).paddingRight) || 0 : 0;
	return {
		clipX: c && isOverlapping ? c.left - r.left + padL + Math.min(c.width - padL - padR, COPY_MAX_W) + 40 : 0,
		// the front of the globe, a little up and left of centre where the sphere faces the viewer
		anchor: { x: view.cx - view.R * 0.25, y: view.cy - view.R * 0.2 },
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
				const base = heroView(w, h);
				const layout = measure(canvas, base);
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
				if (layout.clipX > 0) {
					// soften the cut at the copy column so the sphere does not end on a straight line
					const fade = ctx.createLinearGradient(layout.clipX, 0, layout.clipX + FADE_PX, 0);
					fade.addColorStop(0, "rgba(0,0,0,1)");
					fade.addColorStop(1, "rgba(0,0,0,0)");
					ctx.globalCompositeOperation = "destination-out";
					ctx.fillStyle = fade;
					ctx.fillRect(layout.clipX, 0, FADE_PX, h);
					ctx.globalCompositeOperation = "source-over";
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
			className="hero-globe absolute inset-0 block h-full w-full max-[900px]:relative max-[900px]:inset-auto max-[900px]:order-first max-[900px]:h-[clamp(220px,42vw,320px)]"
		/>
	);
}
