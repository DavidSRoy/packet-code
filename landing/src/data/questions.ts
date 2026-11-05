export interface Question {
	q: string;
	a: string;
}

/** Questions a neighbor would ask, in the order a neighbor would ask them. */
export const QUESTIONS: readonly Question[] = [
	{
		q: "Is it safe?",
		a: "Vehicle 01 flies under the FAA's rules for small unmanned aircraft, on routes Dispatch plans in advance and follows from pickup to drop-off.",
	},
	{
		q: "How loud is it?",
		a: "It is overhead for seconds, not minutes. We will publish noise measurements before the first flight.",
	},
	{
		q: "Where does it land?",
		a: "At the spot you chose in the app, with open sky above it. It sets the order down and leaves.",
	},
	{
		q: "What if I'm not home?",
		a: "It is left at your spot, like a package. The app shows you when it arrived.",
	},
	{
		q: "What about rain and wind?",
		a: "Flights pause in heavy rain and high wind. The app says so before you order.",
	},
	{
		q: "Does it record my street?",
		a: "The aircraft uses its sensors to fly and to land at your spot. Packet does not sell data, and the privacy page says what is kept.",
	},
	{
		q: "Who is flying it?",
		a: "Packet's own team in Seattle, with Dispatch watching every flight.",
	},
];
