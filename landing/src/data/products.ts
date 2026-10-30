import { AppPhone } from "@/components/drawings/AppPhone";
import { DispatchMap } from "@/components/drawings/DispatchMap";
import { VehicleSide } from "@/components/drawings/VehicleSide";

export interface Product {
	id: "vehicle-01" | "app" | "dispatch";
	no: string;
	name: string;
	line: string;
	linkLabel: string;
	description: string;
	specs: readonly { key: string; value: string }[];
	Drawing: () => React.JSX.Element;
}

export const PRODUCTS: readonly Product[] = [
	{
		id: "vehicle-01",
		no: "01",
		name: "Vehicle 01",
		line: "The four-rotor aircraft that carries each order. Payload [TBD].",
		linkLabel: "About Vehicle 01",
		description:
			"The aircraft that carries each order. It lifts off at the shop, flies above the street grid along a planned route, and sets the order down at your door.",
		specs: [
			{ key: "Rotors", value: "4" },
			{ key: "Payload", value: "[TBD]" },
			{ key: "Range", value: "[TBD]" },
			{ key: "Cruise speed", value: "[TBD]" },
			{ key: "Flight altitude", value: "[TBD]" },
			{ key: "Weather limits", value: "[TBD]" },
		],
		Drawing: VehicleSide,
	},
	{
		id: "app",
		no: "02",
		name: "Packet for iPhone",
		line: "Order from U Village shops and follow each step to your door.",
		linkLabel: "About the app",
		description:
			"Where you order and follow it. Choose from U Village shops, pay, and see each step from pickup to your door, with the time it will arrive.",
		specs: [
			{ key: "Platform", value: "iPhone" },
			{ key: "Availability", value: "App Store, [LAUNCH DATE]" },
			{ key: "Order from", value: "U Village shops" },
			{ key: "Delivery area", value: "University Village and the streets around it" },
			{ key: "Payment", value: "[TBD]" },
		],
		Drawing: AppPhone,
	},
	{
		id: "dispatch",
		no: "03",
		name: "Dispatch",
		line: "Plans each flight and follows it from pickup to drop-off.",
		linkLabel: "About dispatch",
		description:
			"The system behind each flight. It assigns an aircraft to every order, plans the route and altitude, and follows the flight until the order is delivered.",
		specs: [
			{ key: "Assigns", value: "One aircraft per order" },
			{ key: "Plans", value: "Route and altitude for each flight" },
			{ key: "Follows", value: "Each flight from pickup to drop-off" },
			{ key: "Hours", value: "[TBD]" },
		],
		Drawing: DispatchMap,
	},
];
