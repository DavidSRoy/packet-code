import { LeadingLines } from "@/components/site/LeadingLines";

export function WhatSection() {
	return (
		<section aria-labelledby="what" className="pad py-[clamp(72px,10vw,120px)]">
			<h2
				id="what"
				className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
			>
				Delivery from U Village shops to homes nearby.
			</h2>
			<LeadingLines />
			<p className="m-0 mt-8 max-w-[60ch]">
				Order in the Packet app, follow it as it comes, and find it at your front door. Packet starts in
				University Village and the streets around it, including the U District and Bryant.
			</p>
		</section>
	);
}
