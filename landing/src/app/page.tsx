import { ClosingCta } from "@/components/home/ClosingCta";
import { Hero } from "@/components/home/Hero";
import { HowItWorks } from "@/components/home/HowItWorks";
import { Mission } from "@/components/home/Mission";
import { Showcase } from "@/components/home/Showcase";
import { WhatSection } from "@/components/home/WhatSection";

export default function Home() {
	return (
		<main>
			<Hero />
			<WhatSection />
			<HowItWorks />
			<Mission />
			<Showcase />
			<ClosingCta />
		</main>
	);
}
