import Link from "next/link";
import { VehicleSide } from "@/components/drawings/VehicleSide";
import { PRODUCTS } from "@/data/products";

const VEHICLE = PRODUCTS[0];
/** The facts the team has given; the rows still marked to follow stay on Products. */
const FACTS = VEHICLE.specs.filter((row) => !row.value.startsWith("["));

/** The first product, as one section: the aircraft gets its reveal after the premise, not before it. */
export function FirstProduct() {
	return (
		<section
			aria-labelledby="first-h"
			className="pad grid grid-cols-[minmax(0,5fr)_minmax(0,7fr)] items-center gap-12 border-t-[1.5px] border-ink py-section max-[760px]:grid-cols-[minmax(0,1fr)] max-[760px]:gap-8"
		>
			<div className="flex flex-col gap-5">
				<span className="lbl">{VEHICLE.no}</span>
				<h2
					id="first-h"
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
				>
					The first product: {VEHICLE.name}.
				</h2>
				<p className="m-0 max-w-[60ch]">{VEHICLE.description}</p>
				<dl className="m-0 flex max-w-[440px] flex-col border-t border-ink">
					{FACTS.map((row) => (
						<div
							key={row.key}
							className="grid grid-cols-[minmax(0,150px)_minmax(0,1fr)] items-baseline gap-4 border-b border-ink py-3"
						>
							<dt className="lbl">{row.key}</dt>
							<dd className="m-0">{row.value}</dd>
						</div>
					))}
				</dl>
				<div className="flex flex-wrap gap-6">
					<Link className="textlink" href={`/products#${VEHICLE.id}`}>
						About {VEHICLE.name}
					</Link>
					<Link className="textlink" href="/products">
						See the app and Dispatch
					</Link>
				</div>
			</div>
			<div className="grid place-items-center py-6 [&_svg]:w-full [&_svg]:max-w-[620px]">
				<VehicleSide />
			</div>
		</section>
	);
}
