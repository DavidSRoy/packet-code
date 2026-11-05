import { ItemBowl } from "@/components/drawings/ItemBowl";
import { ItemBox } from "@/components/drawings/ItemBox";
import { ItemCup } from "@/components/drawings/ItemCup";
import { ItemWrap } from "@/components/drawings/ItemWrap";

export interface LandingItem {
	name: string;
	/** What kind of thing it is, until shops and prices are real. */
	kind: string;
	Drawing: () => React.JSX.Element;
}

/** What you can get: the first items, drawn, with a kind each. Shops and prices live on Products once they are real. */
export const LANDING_ITEMS: readonly LandingItem[] = [
	{ name: "U Village Bowl", kind: "Lunch", Drawing: ItemBowl },
	{ name: "Drumstick Wrap", kind: "Lunch", Drawing: ItemWrap },
	{ name: "Cold Brew", kind: "Coffee", Drawing: ItemCup },
	{ name: "Anything that fits", kind: "In-between", Drawing: ItemBox },
];
