"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
	href: string;
	label: string;
}

const ITEMS: readonly NavItem[] = [
	{ href: "/products", label: "Products" },
	{ href: "/press", label: "Press" },
	{ href: "/#updates", label: "Get updates" },
];

export function Nav() {
	const pathname = usePathname();
	const isHome = pathname === "/";
	return (
		<nav className="pad flex h-14 items-center gap-4 min-[761px]:gap-8" aria-label="Main">
			{isHome ? (
				<span className="mr-auto" />
			) : (
				<Link className="mr-auto font-display text-[20px] font-semibold no-underline" href="/">
					Packet
				</Link>
			)}
			{ITEMS.map((item) =>
				// A hash link has to be a plain anchor: Next's Link changes the URL on the same page without firing
				// hashchange, so the sign-up form never scrolled into view or took focus.
				item.href.includes("#") ? (
					<a key={item.href} className="navlink" href={item.href}>
						{item.label}
					</a>
				) : (
					<Link
						key={item.href}
						className="navlink"
						href={item.href}
						aria-current={pathname === item.href ? "page" : undefined}
					>
						{item.label}
					</Link>
				),
			)}
		</nav>
	);
}
