"use client";

import { useRef } from "react";
import { FirstAreaPlan } from "@/components/drawings/FirstAreaPlan";
import { useLockProgress } from "./useLockProgress";

/** Where Packet flies first: the plan of the first area, scroll-locked while it draws itself. */
export function FirstArea() {
	const sectionRef = useRef<HTMLElement>(null);
	const stageRef = useRef<HTMLDivElement>(null);
	const isLocked = useLockProgress(sectionRef, stageRef, 2.4);

	return (
		<section ref={sectionRef} aria-labelledby="where-h" className={`lock${isLocked ? " is-locked" : ""}`}>
			<div
				ref={stageRef}
				className="lock-stage pad grid grid-cols-[minmax(0,7fr)_minmax(0,5fr)] items-center gap-12 max-[900px]:grid-cols-[minmax(0,1fr)] max-[900px]:gap-7"
			>
				<FirstAreaPlan />
				<div className="flex flex-col gap-6">
					<h2
						id="where-h"
						className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
					>
						Where Packet flies first.
					</h2>
					<p className="m-0 max-w-[60ch]">
						Packet is running in the university area first. The first flights cover University Village, the U
						District, Bryant, Mercer Court and the north campus.
					</p>
					<p className="rise m-0 max-w-[60ch]" data-plan-step="6">
						The streets around them come next, and the map grows as each one is added.
					</p>
					<a className="rise textlink" data-plan-step="6" href="#updates">
						<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
							<path d="M10 18V3M4 9l6-6 6 6" />
						</svg>
						Check your street
					</a>
				</div>
			</div>
		</section>
	);
}
