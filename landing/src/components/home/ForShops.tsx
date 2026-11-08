import { SignButton } from "@/components/site/SignButton";
import { TextField } from "./TextField";

/** PROTOTYPE for the mockup only: the For shops section, above the closing piece. */
export function ForShops() {
	return (
		<section id="shops" aria-labelledby="shops-h" className="pad py-section">
			<div className="grid grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-16 border-t-[8px] border-ink pt-12 max-[900px]:grid-cols-1 max-[900px]:gap-10">
				<div className="flex flex-col gap-5">
					<span className="lbl">For shops</span>
					<h2
						id="shops-h"
						className="m-0 max-w-[16ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
					>
						Run a shop near U&nbsp;Village?
					</h2>
					<p className="m-0 max-w-[40ch] text-[20px] leading-[1.45]">
						Packet starts with a handful of shops around University Village. Tell us about yours and we will be in
						touch before the first deliveries.
					</p>
				</div>
				<form noValidate className="flex flex-col gap-7 self-end">
					<div className="flex flex-wrap gap-6 max-[760px]:flex-col">
						<TextField id="shop-name" label="Shop name" name="shop" placeholder="Your shop" />
						<TextField id="shop-contact" label="Your name" name="name" autoComplete="name" placeholder="First and last" />
					</div>
					<div className="flex flex-wrap gap-6 max-[760px]:flex-col">
						<TextField id="shop-email" label="Email" name="email" type="email" autoComplete="email" placeholder="you@yourshop.com" />
						<TextField id="shop-phone" label="Phone (optional)" name="phone" type="tel" autoComplete="tel" placeholder="(206) 555-0100" />
					</div>
					<div className="flex items-end gap-6 max-[760px]:flex-col max-[760px]:items-start">
						<TextField id="shop-sells" label="What you sell (optional)" name="sells" placeholder="Coffee, lunch, flowers…" />
						<SignButton label="Get in touch" type="submit" />
					</div>
					<p className="m-0 min-h-6 text-[14px]">We only use this to talk to you about Packet.</p>
				</form>
			</div>
		</section>
	);
}
