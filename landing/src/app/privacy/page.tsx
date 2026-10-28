import type { Metadata } from "next";

export const metadata: Metadata = {
	title: "Privacy | Packet",
	description: "What Packet collects when you check your address or sign up, and why.",
};

interface Block {
	id: string;
	title: string;
	paragraphs: readonly string[];
}

const BLOCKS: readonly Block[] = [
	{
		id: "collected",
		title: "What we collect",
		paragraphs: [
			"When you sign up for updates, we store your email address. If you checked an address first, we also store whether it is inside the area Packet plans to serve and its location rounded to about 1 km. We do not store the address you typed.",
			"We also store the campaign tags in the link you arrived from (utm_source, utm_medium and utm_campaign) and the page that referred you, when your browser provides them. Your browser holds these for the length of the visit and sends them with your sign-up. They are not sent anywhere else.",
			"We keep the date you first signed up and the date of your latest sign-up.",
		],
	},
	{
		id: "why",
		title: "Why",
		paragraphs: [
			"We use your email to tell you when Packet reaches your street. We use the area flag, the rounded location and the campaign tags to learn where interest is and which flyers and ads work.",
		],
	},
	{
		id: "address",
		title: "Your address",
		paragraphs: [
			"To find an address you type into the check, our server sends it to Nominatim, the search service run by OpenStreetMap. The address is not stored, by us or in our database. If you then sign up, we look it up again to work out the flag and rounded location above, and discard it.",
		],
	},
	{
		id: "visits",
		title: "Visits",
		paragraphs: [
			"We count page visits with Cloudflare Web Analytics, which does not use cookies. We do not use advertising pixels.",
		],
	},
	{
		id: "sold",
		title: "Selling data",
		paragraphs: ["We do not sell your data."],
	},
	{
		id: "removal",
		title: "Removal",
		paragraphs: ["To be removed, email [CONTACT EMAIL] from the address you signed up with."],
	},
];

export default function PrivacyPage() {
	return (
		<main aria-labelledby="privacy-h" className="pad flex flex-col gap-12 pb-[120px] pt-[72px]">
			<header className="flex max-w-[640px] flex-col gap-4">
				<h1
					id="privacy-h"
					className="m-0 font-display text-[clamp(40px,5vw,64px)] font-semibold leading-[1.05]"
				>
					Privacy
				</h1>
				<p className="m-0 text-[20px] leading-[1.45]">What Packet collects, and what it does with it.</p>
			</header>
			{BLOCKS.map((block) => (
				<section
					key={block.id}
					aria-labelledby={`${block.id}-h`}
					className="flex max-w-[720px] flex-col gap-4 border-t-[1.5px] border-ink pt-6"
				>
					<h2 id={`${block.id}-h`} className="m-0 font-display text-[24px] font-semibold leading-[1.2]">
						{block.title}
					</h2>
					{block.paragraphs.map((text) => (
						<p key={text} className="m-0 max-w-[60ch]">
							{text}
						</p>
					))}
				</section>
			))}
			<section
				aria-labelledby="credits-h"
				className="flex max-w-[720px] flex-col gap-4 border-t-[1.5px] border-ink pt-6"
			>
				<h2 id="credits-h" className="m-0 font-display text-[24px] font-semibold leading-[1.2]">
					Map credits
				</h2>
				<p className="m-0 max-w-[60ch]">
					Map data ©{" "}
					<a
						className="underline underline-offset-[3px]"
						href="https://www.openstreetmap.org/copyright"
						rel="noopener noreferrer"
					>
						OpenStreetMap contributors
					</a>
					. The street lines on the home page globe come from OpenStreetMap, and address lookups use its
					Nominatim service.
				</p>
			</section>
		</main>
	);
}
