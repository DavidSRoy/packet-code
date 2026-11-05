"use client";

import { DeliveryStage } from "./DeliveryStage";
import { PinnedSection } from "./PinnedSection";

/**
 * Why: the premise, pinned. As the reader scrolls, the package lifts off at the shop, crosses above
 * the street and sets down at the door, and each benefit arrives at the moment that proves it.
 */
export function Delivery() {
	return (
		<PinnedSection length={2} labelledBy="why-h">
			{(pin) => <DeliveryStage progress={pin.progress} />}
		</PinnedSection>
	);
}
