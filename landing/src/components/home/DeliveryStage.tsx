"use client";

import { useEffect, useRef } from "react";
import { DeliveryRoute } from "@/components/drawings/DeliveryRoute";
import { ramp } from "@/lib/pin";

interface Benefit {
	title: string;
	text: string;
}

const BENEFITS: readonly Benefit[] = [
	{ title: "Minutes, not an hour.", text: "From the shop to your door, straight over the street." },
	{ title: "Nothing on your street.", text: "No car, no bike, no double-parking. One aircraft above it." },
	{ title: "Set down, not handed off.", text: "Left at your spot. Bring it in when you're ready." },
];

/** The package is on the move for this band of the pin; before it rests at the shop, after it rests at the door. */
const TRAVEL_START = 0.06;
const TRAVEL_END = 0.86;

interface Props {
	/** 0 to 1 through the pin. The benefits read it from the section's `--p`; the package needs it here. */
	progress: number;
}

/** The delivery section's stage: the copy, and the drawing whose package travels the route with the progress. */
export function DeliveryStage(props: Props) {
	const stageRef = useRef<HTMLDivElement>(null);
	const partsRef = useRef<{ route: SVGPathElement; pkg: SVGGElement; length: number } | null>(null);

	useEffect(() => {
		if (!partsRef.current) {
			const route = stageRef.current?.querySelector<SVGPathElement>("path.route");
			const pkg = stageRef.current?.querySelector<SVGGElement>("g.pkg");
			if (!route || !pkg) return;
			partsRef.current = { route, pkg, length: route.getTotalLength() };
		}
		const { route, pkg, length } = partsRef.current;
		const point = route.getPointAtLength(ramp(props.progress, TRAVEL_START, TRAVEL_END) * length);
		pkg.setAttribute("transform", `translate(${point.x.toFixed(1)} ${point.y.toFixed(1)})`);
	}, [props.progress]);

	return (
		<div
			ref={stageRef}
			className="grid grid-cols-[minmax(0,5fr)_minmax(0,7fr)] items-center gap-12 max-[900px]:grid-cols-[minmax(0,1fr)] max-[900px]:gap-7"
		>
			<div className="flex flex-col gap-6">
				<h2
					id="why-h"
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
				>
					Autonomous delivery, built around the way you live.
				</h2>
				<ul className="m-0 flex max-w-[48ch] list-none flex-col gap-5 p-0">
					{BENEFITS.map((benefit, i) => (
						<li key={benefit.title} className="rise flex flex-col gap-1" data-benefit={i + 1}>
							<b className="text-[22px] leading-[1.3]">{benefit.title}</b>
							<span>{benefit.text}</span>
						</li>
					))}
				</ul>
				<p className="rise m-0 max-w-[60ch]" data-benefit="4">
					Vehicle 01 is the first step: a four-rotor aircraft that flies an order from the shop to your door.
				</p>
			</div>
			<div className="max-[900px]:order-first">
				<DeliveryRoute />
			</div>
		</div>
	);
}
