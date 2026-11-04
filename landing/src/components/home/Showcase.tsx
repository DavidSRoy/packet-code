"use client";

import Link from "next/link";
import { useRef, useState, type PointerEvent } from "react";
import { PRODUCTS } from "@/data/products";
import { sliceAt, sliceFill } from "@/lib/pin";
import { PinnedSection } from "./PinnedSection";
import type { Pin } from "./usePinProgress";

const SWIPE_PX = 48;
const COUNT = PRODUCTS.length;
/** Where a control lands inside a product's slice: just past its start, so the reader sees it all. */
const SLICE_ENTRY = 0.05;

export function Showcase() {
	return (
		<PinnedSection length={COUNT} labelledBy="system-h">
			{(pin) => <ShowcaseStage pin={pin} />}
		</PinnedSection>
	);
}

interface StageProps {
	pin: Pin;
}

/** Pinned, scroll picks the product and the controls scroll to it. Unpinned, the controls pick it. */
function ShowcaseStage(props: StageProps) {
	const pin = props.pin;
	const [chosen, setChosen] = useState(0);
	const swipeStartX = useRef<number | null>(null);
	const index = pin.isPinned ? sliceAt(pin.progress, COUNT) : chosen;
	const nextProduct = PRODUCTS[(index + 1) % COUNT];

	function go(i: number): void {
		const target = ((i % COUNT) + COUNT) % COUNT;
		if (pin.isPinned) pin.scrollToProgress((target + SLICE_ENTRY) / COUNT);
		else setChosen(target);
	}

	function onStagePointerDown(e: PointerEvent<HTMLDivElement>): void {
		swipeStartX.current = e.clientX;
	}

	function onStagePointerUp(e: PointerEvent<HTMLDivElement>): void {
		const start = swipeStartX.current;
		swipeStartX.current = null;
		if (start === null || Math.abs(e.clientX - start) <= SWIPE_PX) return;
		go(index + (e.clientX < start ? 1 : -1));
	}

	return (
		<>
			<h2
				id="system-h"
				className="m-0 max-w-[24ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
			>
				One system, from the shop to your door.
			</h2>
			<div aria-roledescription="carousel" aria-label="Packet products" className="mt-12">
				<div
					className="relative grid min-h-[min(clamp(400px,38vw,540px),55svh)] touch-pan-y overflow-hidden -mr-[max(var(--spacing-margin),env(safe-area-inset-right,0px))] max-[760px]:min-h-0"
					aria-live="polite"
					onPointerDown={onStagePointerDown}
					onPointerUp={onStagePointerUp}
				>
					{PRODUCTS.map((product, i) => {
						const isOn = i === index;
						return (
							<article
								key={product.id}
								id={`slide-${product.id}`}
								role="group"
								aria-roledescription="slide"
								aria-label={`${i + 1} of ${COUNT}: ${product.name}`}
								className="sc-slide"
								data-on={isOn}
								inert={!isOn}
							>
								<div className="sc-copy">
									<span className="lbl">{product.no}</span>
									<h3 className="m-0 font-display text-[clamp(40px,5vw,72px)] font-semibold leading-[1.02] tracking-[-0.02em]">
										{product.name}
									</h3>
									<p className="m-0 max-w-[32ch] text-[20px] leading-[1.45]">{product.line}</p>
									<Link
										href={`/products#${product.id}`}
										className="self-start py-1 text-[15px] font-bold underline decoration-[1.5px] underline-offset-[5px]"
									>
										{product.linkLabel}
									</Link>
								</div>
								<div className="sc-art">
									<product.Drawing />
								</div>
							</article>
						);
					})}
					<div className="sc-peek" aria-hidden="true">
						<nextProduct.Drawing />
					</div>
					<button
						type="button"
						aria-label={`Next: ${nextProduct.name}`}
						className="sc-next"
						onClick={() => go(index + 1)}
					>
						<span className="flex flex-col gap-0.5 text-[15px] font-bold max-[760px]:hidden">
							<span className="lbl !text-[12px]">Next</span>
							<span>{nextProduct.name}</span>
						</span>
						<span className="sc-next-arrow" aria-hidden="true">
							<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
								<path d="M2 10h15M11 4l6 6-6 6" />
							</svg>
						</span>
					</button>
				</div>
				<div className="mt-6 flex gap-2">
					{PRODUCTS.map((product, i) => {
						const fill = pin.isPinned ? sliceFill(pin.progress, i, COUNT) : i <= index ? 1 : 0;
						return (
							<button
								key={product.id}
								type="button"
								aria-controls={`slide-${product.id}`}
								aria-label={`Show ${product.name}`}
								aria-current={i === index}
								className="sc-tab"
								onClick={() => go(i)}
							>
								<i>
									<b style={{ transform: `scaleX(${fill})` }} />
								</i>
							</button>
						);
					})}
				</div>
			</div>
		</>
	);
}
