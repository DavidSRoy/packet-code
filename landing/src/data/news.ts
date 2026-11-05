export interface NewsEntry {
	date: string;
	headline: string;
	summary: string;
}

export const NEWS: readonly NewsEntry[] = [
	{
		date: "[DATE]",
		headline: "Packet plans autonomous delivery for University Village",
		summary: "Packet will deliver orders from U Village shops to nearby homes by aircraft.",
	},
	{
		date: "[DATE]",
		headline: "Packet for iPhone opens sign-ups",
		summary:
			"People near U Village can check their address and get an email when Packet reaches their street.",
	},
];
