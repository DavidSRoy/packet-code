"use client";

import { AddressForm } from "./AddressForm";
import { HeroGlobe } from "./HeroGlobe";
import { useSignupFlow } from "./useSignupFlow";

export function Hero() {
	const flow = useSignupFlow();

	return (
		<header
			id="top"
			className="relative min-h-[clamp(520px,72vh,760px)] overflow-hidden max-[900px]:flex max-[900px]:min-h-0 max-[900px]:flex-col"
		>
			<HeroGlobe target={flow.target} />
			<div
				data-hero-copy
				className="pad relative z-[1] box-content flex max-w-[440px] flex-col gap-6 pb-16 pt-[clamp(40px,9vh,112px)] max-[900px]:max-w-none max-[900px]:pb-14 max-[900px]:pt-4"
			>
				<h1 className="m-0 font-display text-[clamp(64px,9vw,136px)] font-semibold leading-none tracking-[-0.02em]">
					Packet
				</h1>
				<p className="m-0 max-w-[28ch] text-[22px] leading-[1.35]">
					Autonomous delivery, from nearby shops to your door.
				</p>
				<AddressForm flow={flow} />
			</div>
		</header>
	);
}
