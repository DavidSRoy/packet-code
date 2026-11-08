/** Ease in and out: slow off the mark, slow into place. */
function easeInOutCubic(t: number): number {
	return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

/**
 * Scrolls the window to `top` over a fixed time with an ease, unlike the browser's smooth scroll, whose speed
 * it picks itself. A wheel, touch or key from the reader stops it where it is. Reduced motion jumps.
 */
export function easeScrollTo(top: number, durationMs = 1000): void {
	const target = Math.max(0, Math.min(top, document.documentElement.scrollHeight - window.innerHeight));
	if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
		window.scrollTo({ top: target, behavior: "instant" });
		return;
	}
	const start = window.scrollY;
	const distance = target - start;
	if (Math.abs(distance) < 1) return;
	// Longer trips take a little longer, so a short one never crawls and a long one never lurches.
	const duration = Math.min(1400, durationMs + Math.abs(distance) * 0.15);
	const t0 = performance.now();
	let isStopped = false;
	const stop = () => {
		isStopped = true;
	};
	const events = ["wheel", "touchstart", "keydown"] as const;
	for (const name of events) window.addEventListener(name, stop, { passive: true, once: true });

	function frame(now: number) {
		if (isStopped) return;
		const t = Math.min(1, (now - t0) / duration);
		window.scrollTo({ top: start + distance * easeInOutCubic(t), behavior: "instant" });
		if (t < 1) requestAnimationFrame(frame);
		else for (const name of events) window.removeEventListener(name, stop);
	}
	requestAnimationFrame(frame);
}

/** The top of the section after the hero, where "See what Packet brings" and the scroll cue lead. */
export function scrollPastHero(): boolean {
	const section = document.getElementById("get-h")?.closest("section");
	if (!section) return false;
	easeScrollTo(section.getBoundingClientRect().top + window.scrollY);
	return true;
}
