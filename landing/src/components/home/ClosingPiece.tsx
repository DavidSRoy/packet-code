"use client";

import { Footer } from "@/components/site/Footer";
import { EmailForm } from "./EmailForm";
import { PinnedSection } from "./PinnedSection";
import { ShareLink } from "./ShareLink";
import { TunnelCanvas } from "./TunnelCanvas";

/**
 * The closing call to action and the footer as one framed piece: corner marks at the stage's corners,
 * the tunnel rushing toward its vanishing point behind the form, and the footer inside the same frame.
 * Pinned, so the form arrives as the tunnel comes toward the reader.
 */
export function ClosingPiece() {
	return (
		<PinnedSection length={0.8} labelledBy="cta-h" className="closing" stageClassName="closing-stage">
			{() => (
				<>
					<span className="corner corner-tl" aria-hidden="true" />
					<span className="corner corner-tr" aria-hidden="true" />
					<span className="corner corner-bl" aria-hidden="true" />
					<span className="corner corner-br" aria-hidden="true" />
					<div className="closing-tunnel" aria-hidden="true">
						<TunnelCanvas />
					</div>
					<div className="closing-frame">
						<div className="rise closing-copy relative z-[1] flex max-w-[520px] flex-col gap-5 self-center">
							<h2
								id="cta-h"
								className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
							>
								Hear when Packet reaches your street.
							</h2>
							<EmailForm />
							<p className="m-0 max-w-[60ch]">Sign up now and you will be first in line when Packet reaches your street.</p>
							<p className="m-0 max-w-[60ch]">
								Know a neighbor who would want this? <ShareLink />
							</p>
							<p className="m-0 text-[14px]">Packet for iPhone is coming to the App Store.</p>
						</div>
						<Footer variant="piece" />
					</div>
				</>
			)}
		</PinnedSection>
	);
}
