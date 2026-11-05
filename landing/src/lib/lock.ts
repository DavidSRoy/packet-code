/**
 * Progress through a scroll-locked section, 0 to 1. `top` is the section's top edge relative to the
 * viewport, `height` its full height and `viewport` the viewport height. It is 0 while the section's
 * top is at or below the viewport top, and 1 once the section's bottom has reached the viewport bottom.
 * A section no taller than the viewport has nothing to lock over, so it is always at 1.
 */
export function lockProgress(top: number, height: number, viewport: number): number {
	const span = height - viewport;
	if (span <= 0) return 1;
	return Math.max(0, Math.min(1, -top / span));
}

/** 0 to 1 across the band [a, b] of a progress value, clamped. The same ramp the CSS uses. */
export function ramp(p: number, a: number, b: number): number {
	if (b <= a) return p >= b ? 1 : 0;
	return Math.max(0, Math.min(1, (p - a) / (b - a)));
}
