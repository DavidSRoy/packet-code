"use client";

import { useRef, type ReactNode } from "react";
import { useDrawIn } from "@/components/home/useDrawIn";
import { marksPath } from "@/lib/canvas/marks";

/** The route from the shop's roof, up and over the street, down to the doorstep. Shared with the lock that moves the package along it. */
export const ROUTE_PATH = "M120 140C120 96 150 70 200 70H420C470 70 563 110 563 226";

/** Where the package rests before any scroll has moved it: at the doorstep, the end of the route. */
const PACKAGE_END = "translate(563 226)";
const PACKAGE_HALF = 7;

/** Renders a stroke element twice: the pen pass, then a fainter second pass wobbled differently. */
function twice(render: (extra: string) => ReactNode): ReactNode {
	return (
		<>
			{render("")}
			{render(" pass2")}
		</>
	);
}

/**
 * A delivery in side view, as a sketched technical drawing: the shop at A, the house at B, the route
 * above the street, the package in transit and the landing pad at the doorstep. The lines draw in
 * once; inside the Delivery section the package (`.pkg`) travels the route (`.route`) as the reader
 * scrolls.
 */
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
				{/* the delivery: route and annotations fade in once the buildings have drawn */}
				<g className="late">
					<path className="route" d={ROUTE_PATH} />
					<rect className="dropoff rise" data-benefit="3" x="547" y="236" width="32" height="4" />
					{/* altitude dimension, x 430 */}
					{twice((c) => (
						<path className={`thin${c}`} d="M422 70H438M422 240H438M430 70V240" />
					))}
					<path d="M430 70l-3 8h6zM430 240l-3-8h6z" fill="var(--color-ink)" />
					<text className="dim" transform="translate(448 155) rotate(90)" textAnchor="middle">
						Altitude
					</text>
					<text className="dim" x="120" y="266" textAnchor="middle">
						A · Shop
					</text>
					<text className="dim" x="540" y="266" textAnchor="middle">
						B · Your door
					</text>
					{twice((c) => (
						<path className={`thin${c}`} d="M120 278V302M563 278V302M120 294H262M398 294H563" />
					))}
					<path d="M120 294l8-3v6zM563 294l-8-3v6z" fill="var(--color-ink)" />
					<text className="dim" x="330" y="298" textAnchor="middle">
						A to B
					</text>
				</g>
				{/* the package in transit: the red block inside corner marks, as on the route in How it works */}
				<g className="pkg late" transform={PACKAGE_END}>
					<path className="thin" d={marksPath(0, 0, PACKAGE_HALF)} />
					<rect
						x={-PACKAGE_HALF}
						y={-PACKAGE_HALF}
						width={PACKAGE_HALF * 2}
						height={PACKAGE_HALF * 2}
						fill="var(--color-red)"
					/>
				</g>
			</svg>
			<figcaption>
				<p className="m-0 mt-4 text-[14px] leading-5">Not to scale.</p>
			</figcaption>
		</figure>
	);
}
