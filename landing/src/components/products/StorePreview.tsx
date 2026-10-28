import Link from "next/link";
import { STORE_ITEMS } from "@/data/store-items";

export function StorePreview() {
	return (
		<section aria-labelledby="store-h" className="flex flex-col gap-8 border-t-8 border-ink pt-10">
			<div className="flex max-w-[640px] flex-col gap-4">
				<span className="lbl self-start bg-mustard px-2 py-1 text-[13px] !font-bold leading-4">Preview</span>
				<h2
					id="store-h"
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
				>
					From U Village shops
				</h2>
				<p className="m-0 max-w-[60ch]">
					Some of what Packet will deliver at launch. Shops, items and prices to follow. Orders open in the app.
				</p>
			</div>
			<ul className="m-0 grid list-none grid-cols-4 gap-8 p-0 max-[760px]:grid-cols-2 max-[760px]:gap-x-4 max-[760px]:gap-y-6">
				{STORE_ITEMS.map((item) => (
					<li
						key={item.name}
						className="flex min-w-0 flex-col gap-1 border-t-[1.5px] border-ink pt-3 [&_svg]:mb-2 [&_svg]:h-auto [&_svg]:w-full"
					>
						<item.Drawing />
						<b className="text-[17px]">{item.name}</b>
						<span className="text-[14px]">{item.shop}</span>
						<span className="text-[14px]">{item.price}</span>
					</li>
				))}
			</ul>
			<Link
				href="/#updates"
				className="self-start py-1 text-[15px] font-bold underline decoration-[1.5px] underline-offset-[5px]"
			>
				Get updates when ordering opens
			</Link>
		</section>
	);
}
