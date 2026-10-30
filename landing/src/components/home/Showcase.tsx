"use client";

import Link from "next/link";
import { useRef, type PointerEvent } from "react";
import { PRODUCTS } from "@/data/products";
import { useShowcase } from "./useShowcase";

const DURATION_MS = 7000;
const SWIPE_PX = 48;

export function Showcase() {
	const showcase = useShowcase(PRODUCTS.length, DURATION_MS);
	const swipeStartX = useRef<number | null>(null);
	const nextProduct = PRODUCTS[(showcase.index + 1) % PRODUCTS.length];

	function onStagePointerDown(e: PointerEvent<HTMLDivElement>): void {
		swipeStartX.current = e.clientX;
	}

	function onStagePointerUp(e: PointerEvent<HTMLDivElement>): void {
		const start = swipeStartX.current;
		swipeStartX.current = null;
		if (start === null || Math.abs(e.clientX - start) <= SWIPE_PX) return;
		showcase.go(showcase.index + (e.clientX < start ? 1 : -1));
	}

	return (
		<section aria-labelledby="system-h" className="pad py-[clamp(72px,10vw,120px)]">
			<h2
				id="system-h"
				className="m-0 max-w-[24ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
			>
				One system, from the shop to your door.
			</h2>
			<div
				aria-roledescription="carousel"
				aria-label="Packet products"
				className="mt-12"
				onPointerDown={showcase.restartWait}
				onKeyDown={showcase.restartWait}
				onFocus={showcase.restartWait}
			>
				<div
					className="relative grid min-h-[clamp(400px,38vw,540px)] touch-pan-y overflow-hidden -mr-[max(var(--spacing-margin),env(safe-area-inset-right,0px))] max-[760px]:min-h-0"
					aria-live={showcase.isRunning ? "off" : "polite"}
					onPointerDown={onStagePointerDown}
					onPointerUp={onStagePointerUp}
				>
					{PRODUCTS.map((product, i) => {
						const isOn = i === showcase.index;
						return (
							<article
								key={product.id}
								id={`slide-${product.id}`}
								role="group"
								aria-roledescription="slide"
								aria-label={`${i + 1} of ${PRODUCTS.length}: ${product.name}`}
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
						onClick={showcase.next}
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
				<div className="mt-6 flex items-center gap-4">
					<div className="flex gap-2">
						{PRODUCTS.map((product, i) => {
							const isOn = i === showcase.index;
							return (
								<button
									key={product.id}
									type="button"
									aria-controls={`slide-${product.id}`}
									aria-label={`Show ${product.name}`}
									aria-current={isOn}
									className="sc-tab"
									data-state={isOn ? "on" : i < showcase.index ? "done" : "todo"}
									data-running={showcase.isRunning}
									onClick={() => showcase.go(i)}
								>
									<i key={isOn ? `${showcase.cycle}-${showcase.isRunning}` : "idle"} style={{ animationDuration: `${DURATION_MS}ms` }} />
								</button>
							);
						})}
					</div>
					<button
						type="button"
						aria-label={showcase.isPlaying ? "Pause" : "Play"}
						className="sc-pp"
						onClick={showcase.togglePlay}
					>
						<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" fill="currentColor">
							{showcase.isPlaying ? <path d="M3 2h3v10H3zM8 2h3v10H8z" /> : <path d="M3 1.5l9 5.5-9 5.5z" />}
						</svg>
					</button>
				</div>
			</div>
		</section>
	);
}
