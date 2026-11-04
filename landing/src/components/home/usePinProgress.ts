"use client";

import { useCallback, useEffect, useState, useSyncExternalStore, type RefObject } from "react";
import { pinProgress } from "@/lib/pin";

/** Pinning needs motion allowed and room for a full stage. Otherwise sections render in normal flow. */
const PIN_QUERY = "(prefers-reduced-motion: no-preference) and (min-height: 600px)";

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
	/** Scrolls the window so the section sits at progress p. Does nothing when not pinned. */
	scrollToProgress(p: number): void;
}

/** Scroll progress through a pinned outer section. The single scroll reader for pinned sections. */
export function usePinProgress(ref: RefObject<HTMLElement | null>): Pin {
	const isPinned = useSyncExternalStore(subscribePin, getCanPin, getServerFalse);
	const [progress, setProgress] = useState(0);

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

	return { progress: isPinned ? progress : 1, isPinned, scrollToProgress };
}
