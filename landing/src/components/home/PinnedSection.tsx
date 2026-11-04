"use client";

import { useRef, type ReactNode } from "react";
import { usePinProgress, type Pin } from "./usePinProgress";

interface Props {
	/** Extra screen heights the stage holds for: one per beat of the section's story. */
	length: number;
	/** Id of the section's heading. */
	labelledBy: string;
	children: (pin: Pin) => ReactNode;
}

/**
 * A section whose stage stays on screen while the reader scrolls through it, so its
 * animation plays out before the page moves on. Scrolling stays native. Under reduced
 * motion or on short screens it renders in normal flow at progress 1.
 * See docs/superpowers/specs/2026-11-04-pinned-sections-design.md.
 */
export function PinnedSection(props: Props) {
	const ref = useRef<HTMLElement>(null);
	const pin = usePinProgress(ref);

	return (
		<section
			ref={ref}
			aria-labelledby={props.labelledBy}
			className="relative"
			style={pin.isPinned ? { height: `${(1 + props.length) * 100}svh` } : undefined}
		>
			<div
				className={
					pin.isPinned
						? "pad sticky top-0 flex h-svh flex-col justify-center overflow-hidden py-[clamp(24px,6svh,72px)]"
						: "pad py-[clamp(72px,10vw,120px)]"
				}
			>
				{props.children(pin)}
			</div>
		</section>
	);
}
