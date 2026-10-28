import { EmailForm } from "./EmailForm";
import { TunnelCanvas } from "./TunnelCanvas";

export function ClosingCta() {
	return (
		<section
			aria-labelledby="cta-h"
			className="pad grid min-h-[560px] grid-cols-[minmax(0,5fr)_minmax(0,7fr)] items-stretch max-[760px]:min-h-0 max-[760px]:grid-cols-[minmax(0,1fr)]"
		>
			<div className="flex flex-col justify-center gap-6 py-24 max-[760px]:pb-[72px] max-[760px]:pt-6">
				<h2
					id="cta-h"
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
				>
					Hear when Packet reaches your street.
				</h2>
				<EmailForm />
				<p className="m-0 text-[14px]">Packet for iPhone is coming to the App Store [LAUNCH DATE].</p>
			</div>
			<div className="relative -mr-[max(var(--spacing-margin),env(safe-area-inset-right,0px))] min-h-[420px] max-[760px]:order-first max-[760px]:-ml-[max(var(--spacing-margin),env(safe-area-inset-left,0px))] max-[760px]:min-h-[300px]">
				<TunnelCanvas />
			</div>
		</section>
	);
}
