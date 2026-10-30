import type { Metadata } from "next";
import { ManualSection } from "@/components/press/ManualSection";
import { SpecList, type SpecRow } from "@/components/press/SpecList";
import { Emblem } from "@/components/site/Emblem";
import { NEWS } from "@/data/news";

export const metadata: Metadata = {
	title: "Press | Packet",
	description: "Facts, news and brand files for writing about Packet.",
};

const FACTS: readonly SpecRow[] = [
	{ key: "Company", value: "Packet" },
	{ key: "Founded", value: "[YEAR]" },
	{ key: "Based in", value: "Seattle, Washington" },
	{ key: "Service area", value: "University Village, Seattle, and the streets around it" },
	{ key: "First product", value: "Vehicle 01, a four-rotor delivery aircraft" },
	{ key: "Deliveries begin", value: "[LAUNCH DATE]" },
	{ key: "Leadership", value: "[NAME], [TITLE] · [NAME], [TITLE]" },
];

const CONTACTS: readonly SpecRow[] = [
	{ key: "Press", value: "[NAME], [EMAIL]" },
	{ key: "Photos and interviews", value: "[EMAIL]" },
];

interface Ink {
	name: string;
	hex: string;
	use: string;
	chip: string;
}

const INKS: readonly Ink[] = [
	{ name: "Packet Red", hex: "#B4432F", use: "The block, and nowhere else large.", chip: "bg-red" },
	{ name: "Black", hex: "#111111", use: "Type, rules and the station-sign button.", chip: "bg-ink" },
	{ name: "Mustard", hex: "#D3A13F", use: "Routes and one tag per page.", chip: "bg-mustard" },
	{ name: "White", hex: "#FFFFFF", use: "Every page.", chip: "bg-white" },
];

const SMALL = "text-[14px] leading-5";
const PLATE_ART = "grid h-[200px] place-items-center border border-ink";

export default function PressPage() {
	return (
		<main aria-labelledby="press-h" className="pad flex flex-col gap-12 pb-[120px] pt-[72px]">
			<header className="flex max-w-[640px] flex-col gap-4">
				<h1
					id="press-h"
					className="m-0 font-display text-[clamp(40px,5vw,64px)] font-semibold leading-[1.05]"
				>
					Press
				</h1>
				<p className="m-0 text-[20px] leading-[1.45]">Facts, news and brand files for writing about Packet.</p>
			</header>

			<ManualSection no="1.0" title="Fact sheet">
				<SpecList rows={FACTS} />
			</ManualSection>

			<ManualSection no="2.0" title="News">
				<ol className="m-0 list-none border-t border-ink p-0">
					{NEWS.map((entry) => (
						<li
							key={entry.headline}
							className="grid grid-cols-[minmax(0,160px)_minmax(0,1fr)] gap-4 border-b border-ink py-4 max-[760px]:grid-cols-[minmax(0,1fr)] max-[760px]:gap-1"
						>
							<span className="lbl pt-[3px] text-[13px]">{entry.date}</span>
							<div>
								<b className="text-[19px] leading-[1.3]">{entry.headline}</b>
								<p className="m-0 mt-1.5 text-[15px]">{entry.summary}</p>
							</div>
						</li>
					))}
				</ol>
			</ManualSection>

			<ManualSection no="3.0" title="Brand">
				<div className="grid grid-cols-2 gap-6 max-[760px]:grid-cols-[minmax(0,1fr)]">
					<figure className="m-0 flex flex-col gap-3">
						<div className={`${PLATE_ART} emblem-plate`}>
							<Emblem size={48} />
						</div>
						<figcaption className="flex flex-col gap-1">
							<b>3.1 Emblem</b>
							<span className={SMALL}>
								The wordmark inside four crop marks. Keep the marks; leave clear space of half the cap
								height on every side. Never stretch, recolor or add effects.
							</span>
						</figcaption>
					</figure>
					<figure className="m-0 flex flex-col gap-3">
						<div className={`flex h-[200px] items-center justify-center gap-10 border border-ink`} aria-hidden="true">
							<span className="font-display text-[40px] font-semibold leading-none">Aa</span>
							<span className="font-body text-[40px] leading-none">Aa</span>
							<span className="font-label text-[40px] font-semibold uppercase leading-none">Aa</span>
						</div>
						<figcaption className="flex flex-col gap-1">
							<b>3.2 Typefaces</b>
							<span className={SMALL}>
								Libre Franklin for the name and headlines. Atkinson Hyperlegible Next for text and
								buttons. Barlow Condensed for short capital labels.
							</span>
						</figcaption>
					</figure>
				</div>
				<ul className="m-0 grid list-none grid-cols-4 gap-6 p-0 max-[760px]:grid-cols-2">
					{INKS.map((ink) => (
						<li key={ink.name} className="flex flex-col gap-1">
							<span className={`mb-2 block h-[72px] border border-ink ${ink.chip}`} aria-hidden="true" />
							<b>{ink.name}</b>
							<span className={SMALL}>{ink.hex}</span>
							<span className={SMALL}>{ink.use}</span>
						</li>
					))}
				</ul>
				<p className={`m-0 ${SMALL}`}>Emblem and drawings as SVG and PNG: [DOWNLOAD LINK]</p>
			</ManualSection>

			<ManualSection no="4.0" title="Contact">
				<SpecList rows={CONTACTS} />
			</ManualSection>
		</main>
	);
}
