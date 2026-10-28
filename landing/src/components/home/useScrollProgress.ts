"use client";

import { useEffect, useState, type RefObject } from "react";

function clamp01(x: number): number {
	return Math.max(0, Math.min(1, x));
}

/**
 * 0 to 1 as the element's top rises through the viewport: 0 while its top is at
 * start * innerHeight or lower, 1 once it has moved span * innerHeight above that.
 * Under reduced motion it is 1 (the final state) and nothing listens.
 */
export function useScrollProgress(ref: RefObject<HTMLElement | null>, start = 0.85, span = 0.6): number {
	const [progress, setProgress] = useState(0);

	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		const isStill = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		let frame = 0;
		function update(): void {
			frame = 0;
			if (!el) return;
			if (isStill) {
				setProgress(1);
				return;
			}
			const vh = window.innerHeight;
			setProgress(clamp01((vh * start - el.getBoundingClientRect().top) / (vh * span)));
		}
		function onScroll(): void {
			if (!frame) frame = requestAnimationFrame(update);
		}
		update();
		if (isStill) return;
		window.addEventListener("scroll", onScroll, { passive: true });
		window.addEventListener("resize", onScroll);
		return () => {
			window.removeEventListener("scroll", onScroll);
			window.removeEventListener("resize", onScroll);
			if (frame) cancelAnimationFrame(frame);
		};
	}, [ref, start, span]);

	return progress;
}
