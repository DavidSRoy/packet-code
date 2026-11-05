"use client";

import { useRef, type ReactNode } from "react";
import { usePinProgress, type Pin } from "./usePinProgress";

interface Props {
	/** Extra screen heights the stage holds for: one per beat of the section's story. */
	length: number;
	/** Id of the section's heading. */
	labelledBy: string;
	/** Extra classes on the section, for a section's own styling hooks. */
	className?: string;
	/** Extra classes on the stage. */
	stageClassName?: string;
	children: (pin: Pin) => ReactNode;
}

/**
 * A section whose stage stays on screen while the reader scrolls through it, so its
 * animation plays out before the page moves on. Scrolling stays native. Under reduced
 * motion, on short screens, or when the stage's content would not fit the viewport, it
 * renders in normal flow at progress 1.
 * The pinned layout is CSS (`.pin` in globals.css), so it is right before hydration. The
 * section's `--p` carries the progress for CSS to stage from (its default is 1, the end).
 * See docs/superpowers/specs/2026-11-04-pinned-sections-design.md.
 */
export function PinnedSection(props: Props) {
	const ref = useRef<HTMLElement>(null);
	const pin = usePinProgress(ref);
	const sectionClass = ["pin", pin.isOverflowing ? "pin-flow" : "", props.className ?? ""].filter(Boolean).join(" ");
	const stageClass = ["pin-stage pad", props.stageClassName ?? ""].filter(Boolean).join(" ");

	return (
		<section
			ref={ref}
			aria-labelledby={props.labelledBy}
			className={sectionClass}
			style={{ "--pin-length": props.length, "--p": pin.progress }}
		>
			<div className={stageClass}>{props.children(pin)}</div>
		</section>
	);
}
