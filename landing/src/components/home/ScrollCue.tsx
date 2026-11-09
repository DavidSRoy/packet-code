"use client";

import { useEffect, useState, type MouseEvent } from "react";
import { scrollPastHero } from "@/lib/scroll";

/**
 * The hint that the page goes on: "See more" over two down arrows that light in turn. It fades once the reader
 * has scrolled, and takes them on if they click it.
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
			onClick={onCueClick}
		>
			<span className="lbl text-[13px]">See more</span>
			<span className="scroll-cue-arrows" aria-hidden="true">
				{[0, 1].map((i) => (
					<svg key={i} viewBox="0 0 20 12" fill="none" stroke="currentColor" strokeWidth="2.25">
						<path d="M2 2l8 8 8-8" />
					</svg>
				))}
			</span>
		</a>
	);
}
