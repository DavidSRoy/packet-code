"use client";

import { useRef } from "react";
import { Footer } from "@/components/site/Footer";
import { EmailForm } from "./EmailForm";
import { TunnelCanvas } from "./TunnelCanvas";
import { useLockProgress } from "./useLockProgress";

/**
 * The closing call to action and the footer as one framed piece: corner marks at the block's corners,
 * the tunnel rushing toward its vanishing point behind the form, and the footer inside the same frame.
 * Scroll-locked, so the form arrives as the tunnel comes toward the reader.
 */
export function ClosingPiece() {
	const sectionRef = useRef<HTMLElement>(null);
	const stageRef = useRef<HTMLDivElement>(null);
	const isLocked = useLockProgress(sectionRef, stageRef, 1.8);

	return (
		<section ref={sectionRef} aria-labelledby="cta-h" className={`lock closing${isLocked ? " is-locked" : ""}`}>
			<div ref={stageRef} className="lock-stage closing-stage pad relative grid grid-rows-[minmax(0,1fr)_auto]">
				<span className="corner corner-tl" aria-hidden="true" />
				<span className="corner corner-tr" aria-hidden="true" />
				<span className="corner corner-bl" aria-hidden="true" />
				<span className="corner corner-br" aria-hidden="true" />
				<div className="closing-tunnel" aria-hidden="true">
					<TunnelCanvas />
				</div>
				<div className="rise closing-copy relative z-[1] flex max-w-[520px] flex-col gap-5 self-center">
					<h2
						id="cta-h"
						className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
					>
						Hear when Packet reaches your street.
					</h2>
					<EmailForm />
					<p className="m-0 max-w-[60ch]">Sign up now and you will be first in line when Packet reaches your street.</p>
					<p className="m-0 max-w-[60ch]">Know a neighbor who would want this? Send them the link.</p>
					<p className="m-0 text-[14px]">Packet for iPhone is coming to the App Store.</p>
				</div>
				<Footer variant="piece" />
			</div>
		</section>
	);
}
