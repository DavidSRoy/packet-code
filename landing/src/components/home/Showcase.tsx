"use client";

import { PRODUCTS } from "@/data/products";
import { PinnedSection } from "./PinnedSection";
import { ShowcaseStage } from "./ShowcaseStage";

export function Showcase() {
	return (
		<PinnedSection length={PRODUCTS.length} labelledBy="system-h">
			{(pin) => <ShowcaseStage pin={pin} />}
		</PinnedSection>
	);
}
