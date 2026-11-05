"use client";

import { useCallback, useEffect, useState, useSyncExternalStore, type RefObject } from "react";
import { pinProgress } from "@/lib/pin";

/**
 * Pinning needs motion allowed and room for a full stage. Otherwise sections render in normal flow.
 * Must match the `.pin` media query in globals.css, which owns the pinned layout.
 */
const PIN_QUERY = "(prefers-reduced-motion: no-preference) and (min-height: 600px)";

/** The section's own class for a stage whose content would not fit the viewport. Must match globals.css. */
const FLOW_CLASS = "pin-flow";

function subscribePin(onChange: () => void): () => void {
	const query = window.matchMedia(PIN_QUERY);
	query.addEventListener("change", onChange);
	return () => query.removeEventListener("change", onChange);
}

function getCanPin(): boolean {
	return window.matchMedia(PIN_QUERY).matches;
}

function getServerFalse(): boolean {
	return false;
}

export interface Pin {
	/** 0 to 1 through the pinned stretch. 1 (the finished state) when not pinned. */
	progress: number;
	isPinned: boolean;
	/** True when the stage's content would not fit the viewport, so the section renders in flow instead. */
	isOverflowing: boolean;
	/** Scrolls the window so the section sits at progress p. Does nothing when not pinned. */
	scrollToProgress(p: number): void;
}

/**
 * Scroll progress through a pinned outer section. The single scroll reader for pinned sections.
 * The stage is measured in its pinned layout on mount and on resize: when its content is taller than
 * the viewport (a long section on a short phone) the section gets `.pin-flow` and renders in flow at
 * the finished state, so nothing is hidden behind the stage's edge.
 */
export function usePinProgress(ref: RefObject<HTMLElement | null>): Pin {
	const canPin = useSyncExternalStore(subscribePin, getCanPin, getServerFalse);
	const [isOverflowing, setIsOverflowing] = useState(false);
	const [progress, setProgress] = useState(0);
	const isPinned = canPin && !isOverflowing;

	useEffect(() => {
		const el = ref.current;
		if (!el || !canPin) return;
		function measure(): void {
			if (!el) return;
			const stage = el.querySelector(".pin-stage");
			if (!stage) return;
			// Measured in the pinned layout, whichever layout the section is in right now. Nothing paints in between.
			const hadFlow = el.classList.contains(FLOW_CLASS);
			el.classList.remove(FLOW_CLASS);
			const isTooTall = stage.scrollHeight > window.innerHeight + 1;
			if (hadFlow) el.classList.add(FLOW_CLASS);
			setIsOverflowing(isTooTall);
		}
		measure();
		window.addEventListener("resize", measure);
		return () => window.removeEventListener("resize", measure);
	}, [ref, canPin]);

	useEffect(() => {
		const el = ref.current;
		if (!el || !isPinned) return;
		let frame = 0;
		function update(): void {
			frame = 0;
			if (!el) return;
			const r = el.getBoundingClientRect();
			setProgress(pinProgress(r.top, r.height, window.innerHeight));
		}
		function onScroll(): void {
			if (!frame) frame = requestAnimationFrame(update);
		}
		update();
		window.addEventListener("scroll", onScroll, { passive: true });
		window.addEventListener("resize", onScroll);
		return () => {
			window.removeEventListener("scroll", onScroll);
			window.removeEventListener("resize", onScroll);
			if (frame) cancelAnimationFrame(frame);
		};
	}, [ref, isPinned]);

	const scrollToProgress = useCallback(
		(p: number): void => {
			const el = ref.current;
			if (!el || !isPinned) return;
			const r = el.getBoundingClientRect();
			const travel = r.height - window.innerHeight;
			window.scrollTo({ top: window.scrollY + r.top + p * travel, behavior: "smooth" });
		},
		[ref, isPinned],
	);

	return { progress: isPinned ? progress : 1, isPinned, isOverflowing, scrollToProgress };
}
