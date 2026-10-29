import type { Metadata } from "next";
import { Atkinson_Hyperlegible_Next, Barlow_Condensed, Libre_Franklin } from "next/font/google";
import { AttributionCapture } from "@/components/site/AttributionCapture";
import { Footer } from "@/components/site/Footer";
import { Nav } from "@/components/site/Nav";
import { SketchFilters } from "@/components/site/SketchFilters";
import "./globals.css";

const libreFranklin = Libre_Franklin({
	subsets: ["latin"],
	weight: ["400", "600"],
	variable: "--font-libre-franklin",
	display: "swap",
});

const atkinson = Atkinson_Hyperlegible_Next({
	subsets: ["latin"],
	weight: ["400", "700"],
	variable: "--font-atkinson",
	display: "swap",
});

const barlow = Barlow_Condensed({
	subsets: ["latin"],
	weight: ["600"],
	variable: "--font-barlow",
	display: "swap",
});

const NO_JS_DRAWING = ".drawing{--dash:0px!important}.drawing .late,.drawing .hid,.drawing .ctr{opacity:1!important}";

export const metadata: Metadata = {
	title: "Packet",
	description: "Delivery from U Village shops to homes nearby, by autonomous aircraft.",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	const beaconToken = process.env.NEXT_PUBLIC_CF_BEACON_TOKEN;
	return (
		<html
			lang="en"
			className={`${libreFranklin.variable} ${atkinson.variable} ${barlow.variable}`}
		>
			<head>
				<link rel="icon" href="/favicon.svg" type="image/svg+xml"></link>
				{/* Without JS the drawing never gets its .on class: show the final state. */}
				<noscript>
					<style>{NO_JS_DRAWING}</style>
				</noscript>
			</head>
			<body className="antialiased">
				<SketchFilters />
				<AttributionCapture />
				<div className="h-2 bg-ink" />
				<Nav />
				{children}
				<Footer />
				{beaconToken ? (
					<script
						defer
						src="https://static.cloudflareinsights.com/beacon.min.js"
						data-cf-beacon={JSON.stringify({ token: beaconToken })}
					/>
				) : null}
			</body>
		</html>
	);
}
