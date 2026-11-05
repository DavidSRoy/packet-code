"use client";

import { useEffect, useState, type RefObject } from "react";

/** True once the element's top passes 75% of the viewport height, then stays true. */
export function useDrawIn(ref: RefObject<HTMLElement | null>): boolean {
	const [isIn, setIsIn] = useState(false);

	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		function check(): void {
			if (!el || el.getBoundingClientRect().top >= window.innerHeight * 0.75) return;
			setIsIn(true);
			window.removeEventListener("scroll", check);
			window.removeEventListener("resize", check);
		}
		window.addEventListener("scroll", check, { passive: true });
		window.addEventListener("resize", check);
		check();
		return () => {
			window.removeEventListener("scroll", check);
			window.removeEventListener("resize", check);
		};
	}, [ref]);

	return isIn;
}
