import { marksPath } from "@/lib/canvas/marks";

interface Stop {
	when: string;
	what: string;
}

const STOPS: readonly Stop[] = [
	{ when: "Now", what: "Sign-ups open" },
	{ when: "Next", what: "First test flights" },
	{ when: "Then", what: "First deliveries in the university area" },
	{ when: "After", what: "More of Seattle" },
];

/** The red block inside its corner marks, as on every route: the stop Packet is at now. */
function NowMark() {
	return (
		<svg viewBox="-24 -24 48 48" className="block h-8 w-8 bg-white" aria-hidden="true">
			<rect x="-7" y="-7" width="14" height="14" fill="var(--color-red)" />
			<path d={marksPath(0, 0, 7)} fill="none" stroke="var(--color-ink)" strokeWidth="1.5" />
		</svg>
	);
}

/** What's next: the plan as a route, with the red block at the stop Packet is at now. */
export function WhatsNext() {
	return (
		<section aria-labelledby="next-h" className="pad py-section">
			<h2
				id="next-h"
				className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
			>
				What&rsquo;s next.
			</h2>
			<div className="timeline relative mt-12">
				<ol className="timeline-stops m-0 grid list-none grid-cols-4 gap-10 p-0">
					{STOPS.map((stop, i) => (
						<li key={stop.when} className="flex min-w-0 flex-col items-start gap-2">
							{i === 0 ? (
								<NowMark />
							) : (
								<span className="grid h-8 w-8 place-items-center rounded-full border-[1.5px] border-ink bg-white text-[15px] font-bold">
									{i + 1}
								</span>
							)}
							<span className="lbl">{stop.when}</span>
							<b className="text-[20px] leading-[1.3]">{stop.what}</b>
						</li>
					))}
				</ol>
			</div>
		</section>
	);
}
