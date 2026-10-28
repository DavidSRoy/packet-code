import Link from "next/link";
import { Emblem } from "./Emblem";

export function Footer() {
	const year = new Date().getFullYear();
	return (
		<footer className="pad flex flex-wrap items-end justify-between gap-6 pb-12 pt-[72px]">
			<div className="flex flex-col gap-4">
				<Emblem size={28} />
				<span className="text-sm leading-5">
					&copy; {year} Packet. Seattle, Washington.
				</span>
			</div>
			<div className="flex gap-6">
				<Link className="navlink" href="/products">Products</Link>
				<Link className="navlink" href="/press">Press</Link>
				<Link className="navlink" href="/privacy">Privacy</Link>
			</div>
		</footer>
	);
}
