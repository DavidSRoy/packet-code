"use client";

import { useRef } from "react";
import { PinnedSection } from "./PinnedSection";
import { TripCanvas } from "./TripCanvas";

const STEPS = [
	{ title: "Order", text: "Pick from [VENDOR]'s menu at U Village and pay in the app.", at: 0 },
	{ title: "Follow it", text: "See each step as it happens, with the time it will arrive.", at: 0.5 },
	{ title: "At your door", text: "It's left at your front door. Bring it in when you're ready.", at: 0.999 },
] as const;

/** The trip finishes at this share of the pin, then holds so the reader sees it arrive. */
const TRIP_END = 0.85;

export function HowItWorks() {
	const stepsRef = useRef<HTMLOListElement>(null);

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
							Three steps, all in the app.
						</h2>
						<div className="relative mt-12 h-[200px] max-[760px]:h-[160px]">
							<TripCanvas progress={progress} stepsRef={stepsRef} />
						</div>
						<ol
							ref={stepsRef}
							className="m-0 grid list-none grid-cols-3 gap-x-12 gap-y-10 p-0 max-[760px]:grid-cols-[minmax(0,1fr)]"
						>
							{STEPS.map((step, i) => {
								const isOn = progress >= step.at;
								return (
									<li key={step.title} className="flex min-w-0 flex-col gap-2">
										<span
											data-bullet
											className={`mb-2 grid h-8 w-8 place-items-center rounded-full border-[1.5px] border-ink text-[15px] font-bold transition-[background-color,color] duration-300 ${isOn ? "bg-ink text-white" : ""}`}
										>
											{i + 1}
										</span>
										<b className="text-[19px] leading-[1.3]">{step.title}</b>
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
