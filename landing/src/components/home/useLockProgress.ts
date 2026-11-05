"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { lockProgress } from "@/lib/lock";

const STILL_QUERY = "(prefers-reduced-motion: reduce)";

function clamp01(x: number): number {
	return Math.max(0, Math.min(1, x));
}

/**
 * Drives a scroll-locked section: the section becomes `screens` viewports tall, its stage sticks to the
 * top while the reader scrolls through it, and the section's `--p` custom property runs from 0 to 1 so
 * the CSS can stage what happens. `onProgress` gets the same value for anything CSS cannot do.
 *
 * The lock is off whenever the stage's content would not fit the viewport (small phones): `--p` then
 * runs 0 to 1 as the section scrolls into view, so the same motion plays, unpinned. Under reduced
 * motion `--p` stays at 1, the end state, which is also the CSS default before this runs.
 */
export function useLockProgress(
	sectionRef: RefObject<HTMLElement | null>,
	stageRef: RefObject<HTMLElement | null>,
	screens: number,
	onProgress?: (p: number) => void,
): boolean {
	const [isLocked, setIsLocked] = useState(false);
	const onProgressRef = useRef(onProgress);

	useEffect(() => {
		onProgressRef.current = onProgress;
	}, [onProgress]);

	useEffect(() => {
		const section = sectionRef.current;
		const stage = stageRef.current;
		if (!section || !stage) return;
		const stillQuery = window.matchMedia(STILL_QUERY);
		let isOn = false;
		let frame = 0;
		section.style.setProperty("--screens", String(screens));

		function apply(p: number): void {
			if (!section) return;
			section.style.setProperty("--p", p.toFixed(4));
			onProgressRef.current?.(p);
		}

		function update(): void {
			frame = 0;
			if (!section) return;
			if (stillQuery.matches) {
				apply(1);
				return;
			}
			const r = section.getBoundingClientRect();
			const vh = window.innerHeight;
			apply(isOn ? lockProgress(r.top, r.height, vh) : clamp01((vh * 0.9 - r.top) / (vh * 0.7)));
		}

		function schedule(): void {
			if (!frame) frame = requestAnimationFrame(update);
		}

		function measure(): void {
			if (!stage) return;
			// scrollHeight is the content's height whether or not the stage is pinned to the viewport.
			const fits = stage.scrollHeight <= window.innerHeight + 1;
			const next = fits && !stillQuery.matches;
			if (next !== isOn) {
				isOn = next;
				setIsLocked(next);
			}
			update();
			// The lock changes the section's height on the next render, so measure once more after it.
			schedule();
		}

		measure();
		window.addEventListener("scroll", schedule, { passive: true });
		window.addEventListener("resize", measure);
		stillQuery.addEventListener("change", measure);
		return () => {
			window.removeEventListener("scroll", schedule);
			window.removeEventListener("resize", measure);
			stillQuery.removeEventListener("change", measure);
			if (frame) cancelAnimationFrame(frame);
		};
	}, [sectionRef, stageRef, screens]);

	return isLocked;
}
