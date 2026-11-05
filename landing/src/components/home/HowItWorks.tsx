"use client";

import { useRef } from "react";
import { PinnedSection } from "./PinnedSection";
import { TripCanvas } from "./TripCanvas";

interface Step {
	title: string;
	text: string;
}

const STEPS: readonly Step[] = [
	{ title: "Order", text: "Pick from a nearby shop's menu and pay in the app." },
	{ title: "Pick your spot", text: "A front step, a yard or a balcony with open sky above it. Packet remembers it." },
	{ title: "Follow it", text: "See each step as it happens, with the time it will arrive." },
	{ title: "At your door", text: "It's set down at your spot. Bring it in when you're ready." },
];

/** The trip finishes at this share of the pin, then holds so the reader sees it arrive. */
const TRIP_END = 0.85;

export function HowItWorks() {
	const stepsRef = useRef<HTMLOListElement>(null);
	const last = STEPS.length - 1;

	return (
		<PinnedSection length={2} labelledBy="how">
			{(pin) => {
				const progress = Math.min(1, pin.progress / TRIP_END);
				return (
					<>
						<h2
							id="how"
							className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
						>
							Four steps, all in the app.
						</h2>
						<div className="relative mt-12 h-[180px] max-[760px]:h-[140px]">
							<TripCanvas progress={progress} stepsRef={stepsRef} stopCount={STEPS.length} />
						</div>
						<ol
							ref={stepsRef}
							className="m-0 grid list-none grid-cols-4 gap-x-10 gap-y-10 p-0 max-[760px]:grid-cols-2 max-[760px]:gap-x-6 max-[480px]:grid-cols-[minmax(0,1fr)]"
						>
							{STEPS.map((step, i) => {
								// The icon eases, so it reaches the last stop a little before the progress does.
								const at = i === last ? 0.97 : i / last;
								const isOn = progress >= at;
								return (
									<li key={step.title} className="flex min-w-0 flex-col gap-2">
										<span
											data-bullet
											className={`mb-2 grid h-8 w-8 place-items-center rounded-full border-[1.5px] border-ink text-[15px] font-bold transition-[background-color,color] duration-300 ${isOn ? "bg-ink text-white" : ""}`}
										>
											{i + 1}
										</span>
										<b className="text-[22px] leading-[1.3]">{step.title}</b>
										<span>{step.text}</span>
									</li>
								);
							})}
						</ol>
					</>
				);
			}}
		</PinnedSection>
	);
}
