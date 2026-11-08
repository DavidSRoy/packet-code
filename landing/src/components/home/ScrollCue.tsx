"use client";

import { useEffect, useState, type MouseEvent } from "react";
import { scrollPastHero } from "@/lib/scroll";

/**
 * The hint that the page goes on: a short dotted route pointing down, with the red block travelling it, and a
 * "Scroll" label. It fades once the reader has scrolled, and takes them on if they click it.
 */
export function ScrollCue() {
	const [isGone, setIsGone] = useState(false);

	useEffect(() => {
		function onScroll() {
			setIsGone(window.scrollY > 40);
		}
		onScroll();
		window.addEventListener("scroll", onScroll, { passive: true });
		return () => window.removeEventListener("scroll", onScroll);
	}, []);

	function onCueClick(e: MouseEvent<HTMLAnchorElement>) {
		if (scrollPastHero()) e.preventDefault();
	}

	return (
		<a
			href="#get-h"
			className="scroll-cue"
			data-gone={isGone || undefined}
			aria-label="Scroll to see more"
			onClick={onCueClick}
		>
			<span className="lbl text-[12px]" aria-hidden="true">
				Scroll
			</span>
			<span className="scroll-cue-route" aria-hidden="true">
				<i />
			</span>
		</a>
	);
}
