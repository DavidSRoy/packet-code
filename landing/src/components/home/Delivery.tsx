"use client";

import { useCallback, useRef } from "react";
import { DeliveryRoute } from "@/components/drawings/DeliveryRoute";
import { ramp } from "@/lib/lock";
import { useLockProgress } from "./useLockProgress";

interface Benefit {
	title: string;
	text: string;
}

const BENEFITS: readonly Benefit[] = [
	{ title: "Minutes, not an hour.", text: "From the shop to your door, straight over the street." },
	{ title: "Nothing on your street.", text: "No car, no bike, no double-parking. One aircraft above it." },
	{ title: "Set down, not handed off.", text: "Left at your spot. Bring it in when you're ready." },
];

/** The package is on the move for this band of the lock; before it rests at the shop, after it rests at the door. */
const TRAVEL_START = 0.06;
const TRAVEL_END = 0.86;

/**
 * Why: the premise, scroll-locked. As the reader scrolls, the package lifts off at the shop, crosses
 * above the street and sets down at the door, and each benefit arrives at the moment that proves it.
 */
export function Delivery() {
	const sectionRef = useRef<HTMLElement>(null);
	const stageRef = useRef<HTMLDivElement>(null);
	const partsRef = useRef<{ route: SVGPathElement; pkg: SVGGElement; length: number } | null>(null);

	const onProgress = useCallback((p: number) => {
		if (!partsRef.current) {
			const route = sectionRef.current?.querySelector<SVGPathElement>("path.route");
			const pkg = sectionRef.current?.querySelector<SVGGElement>("g.pkg");
			if (!route || !pkg) return;
			partsRef.current = { route, pkg, length: route.getTotalLength() };
		}
		const { route, pkg, length } = partsRef.current;
		const point = route.getPointAtLength(ramp(p, TRAVEL_START, TRAVEL_END) * length);
		pkg.setAttribute("transform", `translate(${point.x.toFixed(1)} ${point.y.toFixed(1)})`);
	}, []);

	const isLocked = useLockProgress(sectionRef, stageRef, 3, onProgress);

	return (
		<section ref={sectionRef} aria-labelledby="why-h" className={`lock${isLocked ? " is-locked" : ""}`}>
			<div
				ref={stageRef}
				className="lock-stage pad grid grid-cols-[minmax(0,5fr)_minmax(0,7fr)] items-center gap-12 max-[900px]:grid-cols-[minmax(0,1fr)] max-[900px]:gap-7"
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
		</section>
	);
}
