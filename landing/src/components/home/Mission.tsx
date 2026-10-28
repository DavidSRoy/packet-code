import { VehiclePlanSide } from "@/components/drawings/VehiclePlanSide";

export function Mission() {
	return (
		<section
			aria-labelledby="mission-h"
			className="pad grid grid-cols-[minmax(0,5fr)_minmax(0,7fr)] items-center gap-12 py-[clamp(72px,10vw,120px)] max-[760px]:grid-cols-[minmax(0,1fr)]"
		>
			<div className="flex flex-col gap-6">
				<h2
					id="mission-h"
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
				>
					Autonomous delivery, built around the way you live.
				</h2>
				<p className="m-0 max-w-[60ch] text-[20px] leading-[1.45]">
					From point A to point B faster than the road allows, and lighter on the streets you share.
				</p>
				<p className="m-0 max-w-[60ch]">
					Vehicle 01 is the first: a four-rotor aircraft that flies an order from U Village to your door.
				</p>
			</div>
			<VehiclePlanSide />
		</section>
	);
}
