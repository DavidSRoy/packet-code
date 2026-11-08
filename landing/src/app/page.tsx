import { ClosingPiece } from "@/components/home/ClosingPiece";
import { Delivery } from "@/components/home/Delivery";
import { ForShops } from "@/components/home/ForShops";
import { FirstArea } from "@/components/home/FirstArea";
import { FirstProduct } from "@/components/home/FirstProduct";
import { Hero } from "@/components/home/Hero";
import { HowItWorks } from "@/components/home/HowItWorks";
import { Questions } from "@/components/home/Questions";
import { WhatsNext } from "@/components/home/WhatsNext";
import { WhatYouCanGet } from "@/components/home/WhatYouCanGet";

export default function Home() {
	return (
		<main>
			<Hero />
			<WhatYouCanGet />
			<FirstArea />
			<HowItWorks />
			<Delivery />
			<FirstProduct />
			<WhatsNext />
			<Questions />
			<ForShops />
			<ClosingPiece />
		</main>
	);
}
