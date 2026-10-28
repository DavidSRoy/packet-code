"use client";

import { useEffect } from "react";
import { captureAttribution } from "@/lib/attribution";
import { AddressForm } from "./AddressForm";
import { HeroGlobe } from "./HeroGlobe";
import { useSignupFlow } from "./useSignupFlow";

export function Hero() {
	const flow = useSignupFlow();

	useEffect(() => {
		captureAttribution();
	}, []);

	return (
		<header
			id="top"
			className="relative min-h-[clamp(620px,86vh,880px)] overflow-hidden max-[760px]:flex max-[760px]:min-h-0 max-[760px]:flex-col"
		>
			<HeroGlobe target={flow.target} />
			<div
				data-hero-copy
				className="pad relative z-[1] flex max-w-[440px] flex-col gap-6 pb-16 pt-[clamp(40px,9vh,112px)] max-[760px]:max-w-none max-[760px]:pb-14 max-[760px]:pt-4"
			>
				<h1 className="m-0 font-display text-[clamp(64px,9vw,136px)] font-semibold leading-none tracking-[-0.02em]">
					Packet
				</h1>
				<AddressForm flow={flow} />
				<p className="m-0 text-[14px]">Packet for iPhone is coming to the App Store [LAUNCH DATE].</p>
			</div>
		</header>
	);
}
