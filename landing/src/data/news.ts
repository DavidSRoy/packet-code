export interface NewsEntry {
	/** Shown once it is set. Leave it out rather than guess. */
	date?: string;
	headline: string;
	summary: string;
}

export const NEWS: readonly NewsEntry[] = [
	{
		headline: "Packet plans autonomous delivery for University Village",
		summary: "Packet will deliver orders from U Village shops to nearby homes by aircraft.",
	},
	{
		headline: "Packet for iPhone opens sign-ups",
		summary:
			"People near U Village can check their address and get an email when Packet reaches their street.",
	},
];
