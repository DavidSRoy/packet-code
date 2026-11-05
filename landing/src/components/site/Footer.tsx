import Link from "next/link";
import { Emblem } from "./Emblem";

interface Props {
	/** "page" stands on its own at the bottom of a page; "piece" sits inside the landing page's closing frame. */
	variant?: "page" | "piece";
}

export function Footer(props: Props) {
	const isPiece = props.variant === "piece";
	const year = new Date().getFullYear();
	return (
		<footer
			className={
				isPiece
					? "rise closing-foot relative z-[1] flex flex-wrap items-end justify-between gap-6 pt-10"
					: "pad flex flex-wrap items-end justify-between gap-6 pb-12 pt-[72px]"
			}
		>
			<div className="flex flex-col gap-3">
				<Emblem size={28} />
				<span className="text-sm leading-5">
					&copy; {year} Packet. Seattle, Washington.
				</span>
				{isPiece ? (
					<span className="text-sm leading-5">
						<span className="lbl text-[12px]">For shops</span>&nbsp;&nbsp;Run a shop near U Village?{" "}
						<Link href="/press#manual-4-0-h">Get in touch.</Link>
					</span>
				) : null}
			</div>
			<div className="flex gap-6">
				<Link className="navlink" href="/products">Products</Link>
				<Link className="navlink" href="/press">Press</Link>
				<Link className="navlink" href="/privacy">Privacy</Link>
			</div>
		</footer>
	);
}
