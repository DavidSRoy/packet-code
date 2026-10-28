"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

export interface Showcase {
	index: number;
	/** The reader's play/pause choice. Auto-advance also needs reduced motion off and a visible tab. */
	isPlaying: boolean;
	/** Playing, reduced motion off and the tab visible: the wait is actually counting down. */
	isRunning: boolean;
	/** Changes on every (re)start of the wait, so the progress fill can restart with it. */
	cycle: number;
	go(i: number): void;
	next(): void;
	togglePlay(): void;
	restartWait(): void;
}

const STILL_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeStill(onChange: () => void): () => void {
	const query = window.matchMedia(STILL_QUERY);
	query.addEventListener("change", onChange);
	return () => query.removeEventListener("change", onChange);
}

function getIsStill(): boolean {
	return window.matchMedia(STILL_QUERY).matches;
}

function subscribeVisible(onChange: () => void): () => void {
	document.addEventListener("visibilitychange", onChange);
	return () => document.removeEventListener("visibilitychange", onChange);
}

function getIsVisible(): boolean {
	return document.visibilityState === "visible";
}

function getServerFalse(): boolean {
	return false;
}

function getServerTrue(): boolean {
	return true;
}

/**
 * Which product is showing, and the 7s auto-advance. It advances only while playing,
 * with reduced motion off and the tab visible. Returning to the tab restarts a full wait.
 */
export function useShowcase(count: number, durationMs = 7000): Showcase {
	const [index, setIndex] = useState(0);
	const [isPlaying, setIsPlaying] = useState(true);
	const [cycle, setCycle] = useState(0);
	const isStill = useSyncExternalStore(subscribeStill, getIsStill, getServerFalse);
	const isVisible = useSyncExternalStore(subscribeVisible, getIsVisible, getServerTrue);

	const go = useCallback(
		(i: number): void => {
			setIndex(((i % count) + count) % count);
			setCycle((c) => c + 1);
		},
		[count],
	);

	const next = useCallback((): void => {
		setIndex((i) => (i + 1) % count);
		setCycle((c) => c + 1);
	}, [count]);

	const restartWait = useCallback((): void => setCycle((c) => c + 1), []);

	const togglePlay = useCallback((): void => {
		setIsPlaying((p) => !p);
		setCycle((c) => c + 1);
	}, []);

	const isRunning = isPlaying && !isStill && isVisible;
	useEffect(() => {
		if (!isRunning) return;
		const timer = window.setTimeout(next, durationMs);
		return () => window.clearTimeout(timer);
	}, [isRunning, cycle, durationMs, next]);

	return { index, isPlaying, isRunning, cycle, go, next, togglePlay, restartWait };
}
