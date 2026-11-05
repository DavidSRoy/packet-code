import { QUESTIONS } from "@/data/questions";

/** Questions a neighbor would ask: collapsible rows, numbered like the Press manual, the first one open. */
export function Questions() {
	return (
		<section aria-labelledby="faq-h" className="pad flex flex-col gap-8 py-section">
			<div className="flex flex-col gap-4">
				<h2
					id="faq-h"
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
				>
					Questions a neighbor would ask.
				</h2>
				<p className="m-0 max-w-[60ch] text-[20px] leading-[1.45]">
					Packet flies over streets people live on. These are the questions we would ask, and the answers as
					they stand.
				</p>
			</div>
			<div className="faq flex flex-col border-b-[1.5px] border-ink">
				{QUESTIONS.map((item, i) => (
					<details key={item.q} open={i === 0}>
						<summary>
							<span className="lbl">{i + 1}.0</span>
							<span className="faq-q">{item.q}</span>
							<span className="faq-plus" aria-hidden="true" />
						</summary>
						<div className="faq-a">
							<p className="m-0 max-w-[60ch]">{item.a}</p>
						</div>
					</details>
				))}
			</div>
		</section>
	);
}
