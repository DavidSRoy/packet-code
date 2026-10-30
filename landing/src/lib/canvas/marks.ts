import { INK } from "./sphere";

/**
 * Corner marks around a point, as in the emblem. k spreads them (1 is as
 * drawn). hasBlock adds the red block, the app icon.
 */
export function drawMarks(
	ctx: CanvasRenderingContext2D,
	x: number,
	y: number,
	s: number,
	k: number,
	lw: number,
	hasBlock: boolean,
): void {
	if (hasBlock) {
		ctx.fillStyle = INK.red;
		ctx.fillRect(x - s, y - s, 2 * s, 2 * s);
	}
	const B = s * 1.9 * k;
	const off = s * 0.4;
	const len = s * 0.9;
	ctx.strokeStyle = INK.black;
	ctx.lineWidth = lw;
	ctx.beginPath();
	for (const sx of [-1, 1]) {
		for (const sy of [-1, 1]) {
			ctx.moveTo(x + sx * (B + off), y + sy * B);
			ctx.lineTo(x + sx * (B + off + len), y + sy * B);
			ctx.moveTo(x + sx * B, y + sy * (B + off));
			ctx.lineTo(x + sx * B, y + sy * (B + off + len));
		}
	}
	ctx.stroke();
}
