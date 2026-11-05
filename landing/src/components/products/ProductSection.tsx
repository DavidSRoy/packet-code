import type { Product } from "@/data/products";

interface Props {
	product: Product;
	isFlipped: boolean;
}

export function ProductSection(props: Props) {
	const product = props.product;
	const headingId = `${product.id}-h`;
	return (
		<section
			id={product.id}
			aria-labelledby={headingId}
			className="grid scroll-mt-20 grid-cols-[minmax(0,5fr)_minmax(0,7fr)] items-center gap-12 border-t-[1.5px] border-ink pt-10 max-[760px]:grid-cols-[minmax(0,1fr)] max-[760px]:gap-6"
		>
			<div
				className={`flex flex-col gap-4 ${props.isFlipped ? "order-2 max-[760px]:order-none" : ""}`}
			>
				<span className="lbl">{product.no}</span>
				<h2
					id={headingId}
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(36px,4.4vw,60px)] font-semibold leading-[1.04] tracking-[-0.02em]"
				>
					{product.name}
				</h2>
				<p className="m-0 max-w-[60ch]">{product.description}</p>
				<dl className="m-0 mt-2 border-t border-ink">
					{product.specs.map((spec) => (
						<div
							key={spec.key}
							className="grid grid-cols-[minmax(0,160px)_minmax(0,1fr)] gap-4 border-b border-ink py-2.5 max-[760px]:grid-cols-[minmax(0,120px)_minmax(0,1fr)]"
						>
							<dt className="pt-0.5 font-label text-[13px] font-semibold uppercase tracking-[0.08em]">
								{spec.key}
							</dt>
							<dd className="m-0 text-[15px]">{spec.value}</dd>
						</div>
					))}
				</dl>
			</div>
			<div className="[&_svg]:block [&_svg]:h-auto [&_svg]:max-h-[360px] [&_svg]:w-full max-[760px]:order-first">
				<product.Drawing />
			</div>
		</section>
	);
}
