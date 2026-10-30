import { ItemBowl } from "@/components/drawings/ItemBowl";
import { ItemBox } from "@/components/drawings/ItemBox";
import { ItemCup } from "@/components/drawings/ItemCup";
import { ItemWrap } from "@/components/drawings/ItemWrap";

export interface StoreItem {
	name: string;
	shop: string;
	price: string;
	Drawing: () => React.JSX.Element;
}

export const STORE_ITEMS: readonly StoreItem[] = [
	{ name: "U Village Bowl", shop: "[SHOP]", price: "[PRICE]", Drawing: ItemBowl },
	{ name: "Drumstick Wrap", shop: "[SHOP]", price: "[PRICE]", Drawing: ItemWrap },
	{ name: "Cold Brew", shop: "[SHOP]", price: "[PRICE]", Drawing: ItemCup },
	{ name: "[ITEM]", shop: "[SHOP]", price: "[PRICE]", Drawing: ItemBox },
];
