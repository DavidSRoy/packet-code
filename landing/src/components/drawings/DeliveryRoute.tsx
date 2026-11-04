"use client";

import { useRef, type ReactNode } from "react";
import { useDrawIn } from "@/components/home/useDrawIn";

/** Dimension labels only. The drawing is a demonstration, not to scale, so the lines carry no values. */
const SPECS = {
	altitude: "Altitude",
	distance: "A to B",
} as const;

const LEGEND = [
	"Pickup at the shop",
	"The route, above the street",
	"Drop-off at your door",
	"The street below, unchanged",
] as const;

/** Leader line, then the circle's centre. */
const CALLOUTS = [
	{ n: 1, line: "M112 136L84 108", x: 74, y: 98 },
	{ n: 2, line: "M250 62V44", x: 250, y: 34 },
	{ n: 3, line: "M560 212H622", x: 634, y: 212 },
	{ n: 4, line: "M330 238V222", x: 330, y: 210 },
] as const;

/** The package in transit, drawn as on the route in How it works: the red block inside four corner marks. */
const PACKAGE = { x: 330, y: 70, s: 7 } as const;

/** Renders a stroke element twice: the pen pass, then a fainter second pass wobbled differently. */
function twice(render: (extra: string) => ReactNode): ReactNode {
	return (
		<>
			{render("")}
			{render(" pass2")}
		</>
	);
}

/** Corner marks around (x, y), the same proportions as the canvas marks and the emblem. */
function marksPath(x: number, y: number, s: number): string {
	const B = s * 1.9;
	const off = s * 0.4;
	const len = s * 0.9;
	const parts: string[] = [];
	for (const sx of [-1, 1]) {
		for (const sy of [-1, 1]) {
			parts.push(`M${x + sx * (B + off)} ${y + sy * B}H${x + sx * (B + off + len)}`);
			parts.push(`M${x + sx * B} ${y + sy * (B + off)}V${y + sy * (B + off + len)}`);
		}
	}
	return parts.join("");
}

export function DeliveryRoute() {
	const figureRef = useRef<HTMLElement>(null);
	const isIn = useDrawIn(figureRef);

	return (
		<figure ref={figureRef} className={`drawing m-0${isIn ? " on" : ""}`}>
			<svg viewBox="0 0 660 312" role="img" aria-labelledby="dwg-route-t">
				<title id="dwg-route-t">
					Technical drawing of a delivery in side view: a dotted route rises from a shop at A, runs above the
					street with a red package in transit, and sets down at the front door of a house at B
				</title>
				{/* ground, from edge to edge */}
				{twice((c) => (
					<path className={`ln${c}`} d="M20 240H640" pathLength="1" />
				))}
				{/* A: the shop, x 50 to 190 */}
				{twice((c) => (
					<rect className={`ln${c}`} x="50" y="140" width="140" height="100" rx="2" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`ln${c}`} x="70" y="150" width="100" height="16" pathLength="1" />
				))}
				{twice((c) => (
					<path className={`ln${c}`} d="M44 176H196M52 176L58 166M188 176L182 166" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`ln${c}`} x="104" y="198" width="26" height="42" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`thin${c}`} x="146" y="186" width="30" height="24" pathLength="1" />
				))}
				{/* B: the house, x 470 to 610, gable to 112 */}
				{twice((c) => (
					<path className={`ln${c}`} d="M470 240V162H610V240" pathLength="1" />
				))}
				{twice((c) => (
					<path className={`ln${c}`} d="M462 166L540 112L618 166" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`ln${c}`} x="522" y="198" width="28" height="42" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`thin${c}`} x="572" y="184" width="22" height="20" pathLength="1" />
				))}
				{/* the delivery: route, package in transit, drop-off; shows once the buildings have drawn */}
				<g className="late">
					<path className="route" d="M120 140C120 96 150 70 200 70H420C470 70 563 110 563 226" />
					<path className="thin" d={marksPath(PACKAGE.x, PACKAGE.y, PACKAGE.s)} />
					<rect
						x={PACKAGE.x - PACKAGE.s}
						y={PACKAGE.y - PACKAGE.s}
						width={PACKAGE.s * 2}
						height={PACKAGE.s * 2}
						fill="var(--color-red)"
					/>
					{twice((c) => (
						<rect className={`hid${c}`} x="556" y="226" width="14" height="14" />
					))}
					{/* altitude dimension, x 430 */}
					{twice((c) => (
						<path className={`thin${c}`} d="M422 70H438M422 240H438M430 70V240" />
					))}
					<path d="M430 70l-3 8h6zM430 240l-3-8h6z" fill="var(--color-ink)" />
					<text className="dim" transform="translate(448 155) rotate(90)" textAnchor="middle">
						{SPECS.altitude}
					</text>
					{/* labels under the ground */}
					<text className="dim" x="120" y="266" textAnchor="middle">
						A · Shop
					</text>
					<text className="dim" x="540" y="266" textAnchor="middle">
						B · Your door
					</text>
					{/* A to B dimension, y 294, with a gap for the label */}
					{twice((c) => (
						<path className={`thin${c}`} d="M120 278V302M563 278V302M120 294H262M398 294H563" />
					))}
					<path d="M120 294l8-3v6zM563 294l-8-3v6z" fill="var(--color-ink)" />
					<text className="dim" x="330" y="298" textAnchor="middle">
						{SPECS.distance}
					</text>
					{/* callouts: 1 pickup, 2 route, 3 drop-off, 4 street */}
					{CALLOUTS.map((k) => (
						<g key={k.n}>
							{twice((c) => (
								<path className={`thin${c}`} d={k.line} />
							))}
							<g transform={`translate(${k.x} ${k.y})`}>
								<g className="callout">
									<circle cx="0" cy="0" r="10" fill="var(--color-white)" stroke="var(--color-ink)" />
									<text className="num" x="0" y="0">
										{k.n}
									</text>
								</g>
							</g>
						</g>
					))}
				</g>
			</svg>
			<figcaption>
				<ol className="m-0 mt-6 grid list-none grid-cols-2 gap-x-8 gap-y-2 p-0 text-[15px] max-[760px]:grid-cols-[minmax(0,1fr)]">
					{LEGEND.map((text, i) => (
						<li key={text} className="flex items-baseline gap-3">
							<b className="tabular-nums">{i + 1}</b>
							<span>{text}</span>
						</li>
					))}
				</ol>
				<p className="m-0 mt-4 text-[14px] leading-5">Not to scale.</p>
			</figcaption>
		</figure>
	);
}
