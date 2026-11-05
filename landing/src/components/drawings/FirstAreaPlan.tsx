import { PLACES, PLAN } from "@/data/plan";
import { marksPath } from "@/lib/canvas/marks";
import { PLAN_H, PLAN_W } from "@/lib/plan";

const [HUB_X, HUB_Y] = PLAN.hub;
const HUB_HALF = 9;

/**
 * The first area as a plan: dotted streets, the boundary, the red block at the U Village hub and the
 * places named around it. Inside a scroll-locked section the boundary draws, the hub's marks close in
 * and the first-area places appear in order, all from the section's `--p`. No pen filter here: the
 * dotted streets read as drawn already, and the plan has to repaint cheaply while it is pinned.
 */
export function FirstAreaPlan() {
	return (
		<figure className="m-0 flex flex-col gap-3">
			<div className="relative">
				<svg
					viewBox={`0 0 ${PLAN_W} ${PLAN_H}`}
					role="img"
					aria-label="Plan of the first area: dotted streets around University Village, the U District, Bryant and the north campus, with the first area outlined and the U Village hub marked"
					className="block h-auto w-full"
				>
					<path d={PLAN.minor} className="plan-minor" />
					<path d={PLAN.main} className="plan-main" />
					<path d={PLAN.area} pathLength="1" className="ramp plan-bound" />
					<rect
						x={HUB_X - HUB_HALF}
						y={HUB_Y - HUB_HALF}
						width={HUB_HALF * 2}
						height={HUB_HALF * 2}
						fill="var(--color-red)"
						className="ramp plan-block"
					/>
					<path
						d={marksPath(HUB_X, HUB_Y, HUB_HALF)}
						className="ramp plan-marks"
						style={{ transformOrigin: `${HUB_X}px ${HUB_Y}px` }}
					/>
					<path d="M608 48V18M601 28L608 18L615 28" className="plan-thin" />
				</svg>
				<ol className="m-0 list-none p-0" aria-hidden="true">
					{PLACES.map((place) => (
						<li
							key={place.name}
							className="plan-label"
							data-anchor={place.anchor}
							style={{ left: `${(place.x / PLAN_W) * 100}%`, top: `${(place.y / PLAN_H) * 100}%` }}
						>
							<span className={`lbl block${place.step ? " rise" : ""}`} data-plan-step={place.step}>
								{place.name}
							</span>
						</li>
					))}
					<li className="plan-label" style={{ left: "95%", top: "14%" }}>
						<span className="lbl block">N</span>
					</li>
				</ol>
			</div>
			<figcaption className="lbl flex gap-6">
				<span>First area</span>
				<span>Sheet 1</span>
			</figcaption>
		</figure>
	);
}
