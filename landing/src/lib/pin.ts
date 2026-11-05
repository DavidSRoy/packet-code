function clamp01(x: number): number {
	return Math.max(0, Math.min(1, x));
}

/**
 * 0 to 1 while a pinned section's stage holds: 0 as its top reaches the top of
 * the viewport, 1 as its bottom reaches the bottom. top and height are the outer
 * section's bounding box.
 */
export function pinProgress(top: number, height: number, viewport: number): number {
	const travel = height - viewport;
	return travel > 0 ? clamp01(-top / travel) : 1;
}

/** Which of count equal slices progress falls in. Progress 1 stays in the last. */
export function sliceAt(progress: number, count: number): number {
	return Math.min(count - 1, Math.floor(clamp01(progress) * count));
}

/** 0 to 1: how far progress is through slice i of count. */
export function sliceFill(progress: number, i: number, count: number): number {
	return clamp01(progress * count - i);
}

/** 0 to 1 across the band [a, b] of progress, clamped. The same ramp the CSS uses (`--a`, `--b`, `--t`). */
export function ramp(progress: number, a: number, b: number): number {
	if (b <= a) return progress >= b ? 1 : 0;
	return clamp01((progress - a) / (b - a));
}
