import { LeadingLines } from "@/components/site/LeadingLines";
import { LANDING_ITEMS } from "@/data/landing-items";

/** What you can get: the first concrete thing on the page, drawn. The first area is named once, as where Packet starts. */
export function WhatYouCanGet() {
	return (
		<section aria-labelledby="get-h" className="pad flex flex-col py-section">
			<h2
				id="get-h"
				className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
			>
				Lunch, coffee, and anything in-between.
			</h2>
			<LeadingLines />
			<p className="m-0 mt-8 max-w-[60ch] text-[20px] leading-[1.45]">
				Whatever a shop near you sells, Packet can bring it to you wherever you are.
			</p>
			<ul className="sketch-pen3 m-0 mt-10 grid list-none grid-cols-4 gap-10 p-0 max-[760px]:grid-cols-2 max-[760px]:gap-6">
				{LANDING_ITEMS.map((item) => (
					<li key={item.name} className="flex min-w-0 flex-col gap-2 border-t border-ink pt-6 [&_svg]:w-full">
						<item.Drawing />
						<b className="text-[17px]">{item.name}</b>
						<span className="text-[15px]">{item.kind}</span>
					</li>
				))}
			</ul>
			<p className="m-0 mt-8 max-w-[60ch] text-[14px] leading-5">
				Packet starts in University Village and the streets around it, including the U District and Bryant.
			</p>
		</section>
	);
}
