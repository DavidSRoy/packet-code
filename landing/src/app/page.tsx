import { ClosingCta } from "@/components/home/ClosingCta";
import { Hero } from "@/components/home/Hero";
import { HowItWorks } from "@/components/home/HowItWorks";
import { Mission } from "@/components/home/Mission";
import { WhatSection } from "@/components/home/WhatSection";

export default function Home() {
	return (
		<main>
			<Hero />
			<WhatSection />
			<HowItWorks />
			<Mission />
			<ClosingCta />
		</main>
	);
}
