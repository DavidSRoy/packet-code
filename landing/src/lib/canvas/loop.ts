export type DrawFn = (ctx: CanvasRenderingContext2D, w: number, h: number, t: number) => void;

export interface MountOptions {
	isAnimated: boolean;
}

export interface CanvasHandle {
	paint: () => void;
	destroy: () => void;
}

/**
 * Sizes a canvas for the device pixel ratio, repaints on resize, and, when
 * animated, runs a frame loop only while the canvas is on screen and the
 * document is visible. Not animated (reduced motion) means one still frame per
 * resize and no loop at all.
 */
export function mountCanvas(canvas: HTMLCanvasElement, draw: DrawFn, opts: MountOptions): CanvasHandle {
	const ctx = canvas.getContext("2d");
	if (!ctx) {
		console.error("[canvas:mountCanvas] 2D context unavailable — {}");
		return { paint: () => {}, destroy: () => {} };
	}
	const context = ctx;
	let w = 0;
	let h = 0;
	let t = 0;
	let last = 0;
	let frame = 0;
	let isOnScreen = false;

	function paint(): void {
		if (!w || !h) return;
		context.clearRect(0, 0, w, h);
		draw(context, w, h, t);
	}

	function resize(): void {
		const rect = canvas.getBoundingClientRect();
		if (!rect.width || !rect.height) return;
		const dpr = Math.min(2, window.devicePixelRatio || 1);
		w = rect.width;
		h = rect.height;
		canvas.width = Math.round(w * dpr);
		canvas.height = Math.round(h * dpr);
		context.setTransform(dpr, 0, 0, dpr, 0, 0);
		paint();
	}

	function loop(now: number): void {
		frame = 0;
		const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
		last = now;
		t += dt;
		paint();
		frame = requestAnimationFrame(loop);
	}

	function sync(): void {
		const isRunning = isOnScreen && !document.hidden;
		if (isRunning && !frame) {
			last = 0;
			frame = requestAnimationFrame(loop);
		} else if (!isRunning && frame) {
			cancelAnimationFrame(frame);
			frame = 0;
		}
	}

	const resizeObserver = new ResizeObserver(resize);
	resizeObserver.observe(canvas);

	let intersectionObserver: IntersectionObserver | null = null;
	if (opts.isAnimated) {
		intersectionObserver = new IntersectionObserver((entries) => {
			const entry = entries[entries.length - 1];
			isOnScreen = entry ? entry.isIntersecting : false;
			sync();
		});
		intersectionObserver.observe(canvas);
		document.addEventListener("visibilitychange", sync);
	}

	return {
		paint,
		destroy() {
			resizeObserver.disconnect();
			intersectionObserver?.disconnect();
			document.removeEventListener("visibilitychange", sync);
			if (frame) cancelAnimationFrame(frame);
			frame = 0;
		},
	};
}
