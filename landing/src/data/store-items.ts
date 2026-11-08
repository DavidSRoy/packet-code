import { ItemBowl } from "@/components/drawings/ItemBowl";
import { ItemCup } from "@/components/drawings/ItemCup";
import { ItemWrap } from "@/components/drawings/ItemWrap";

export interface StoreItem {
	name: string;
	/** What kind of thing it is. Swap in the shop's name and the price once a shop agrees to be listed. */
	kind: string;
	Drawing: () => React.JSX.Element;
}

/** The first items, drawn. The preview's last card is the open slot for a shop, so this list has three. */
export const STORE_ITEMS: readonly StoreItem[] = [
	{ name: "U Village Bowl", kind: "Lunch", Drawing: ItemBowl },
	{ name: "Drumstick Wrap", kind: "Lunch", Drawing: ItemWrap },
	{ name: "Cold Brew", kind: "Coffee", Drawing: ItemCup },
];
