import type { Metadata } from "next";
import { ProductSection } from "@/components/products/ProductSection";
import { StorePreview } from "@/components/products/StorePreview";
import { PRODUCTS } from "@/data/products";

export const metadata: Metadata = {
	title: "Products | Packet",
	description: "Three parts that take an order from a U Village shop to your door.",
};

export default function ProductsPage() {
	return (
		<main aria-labelledby="products-h" className="pad flex flex-col gap-12 pb-[120px] pt-[72px]">
			<header className="flex max-w-[640px] flex-col gap-4">
				<h1
					id="products-h"
					className="m-0 font-display text-[clamp(40px,5vw,64px)] font-semibold leading-[1.05]"
				>
					Products
				</h1>
				<p className="m-0 text-[20px] leading-[1.45]">
					Three parts that take an order from a U Village shop to your door.
				</p>
			</header>
			{PRODUCTS.map((product, i) => (
				<ProductSection key={product.id} product={product} isFlipped={i % 2 === 1} />
			))}
			<StorePreview />
		</main>
	);
}
