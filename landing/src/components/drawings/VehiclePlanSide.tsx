"use client";

import { useRef, type ReactNode } from "react";
import { useDrawIn } from "@/components/home/useDrawIn";

/** Dimensions and limits to fill in once Vehicle 01 has real specs. */
const SPECS = {
	span: "Span [TBD]",
	height: "Height [TBD]",
	payloadLimit: "[TBD]",
} as const;

const LEGEND = [
	"Rotor, one of four",
	"Body: battery and flight computer",
	`Payload: one order, up to ${SPECS.payloadLimit}`,
	"Landing legs",
] as const;

const CALLOUTS = [
	{ n: 1, line: "M50 310L30 334", x: 24, y: 342 },
	{ n: 2, line: "M182 160V130", x: 182, y: 120 },
	{ n: 3, line: "M518 262H580", x: 590, y: 262 },
	{ n: 4, line: "M456 286L412 266", x: 402, y: 262 },
] as const;

const ROTORS = [
	[90, 110],
	[250, 110],
	[90, 270],
	[250, 270],
] as const;

/** Renders a stroke element twice: the pen pass, then a fainter second pass wobbled differently. */
function twice(render: (extra: string) => ReactNode): ReactNode {
	return (
		<>
			{render("")}
			{render(" pass2")}
		</>
	);
}

export function VehiclePlanSide() {
	const figureRef = useRef<HTMLElement>(null);
	const isIn = useDrawIn(figureRef);

	return (
		<figure ref={figureRef} className={`drawing m-0${isIn ? " on" : ""}`}>
			<svg viewBox="0 0 660 380" role="img" aria-labelledby="dwg-t">
				<title id="dwg-t">
					Technical drawing of Vehicle 01, a four-rotor aircraft, in plan and side view, carrying a red package
					under its body
				</title>
				{/* plan view, centre (170,190) */}
				{twice((c) => (
					<path className={`ctr${c}`} d="M20 190H320M170 40V340" />
				))}
				{ROTORS.map(([cx, cy]) => (
					<g key={`disc-${cx}-${cy}`}>
						{twice((c) => (
							<circle className={`hid${c}`} cx={cx} cy={cy} r="56" />
						))}
					</g>
				))}
				{twice((c) => (
					<path
						className={`ln${c}`}
						d="M145 165L90 110M195 165L250 110M145 215L90 270M195 215L250 270"
						pathLength="1"
					/>
				))}
				{twice((c) => (
					<rect className={`ln${c}`} x="140" y="160" width="60" height="60" rx="6" pathLength="1" />
				))}
				{ROTORS.map(([cx, cy]) => (
					<g key={`hub-${cx}-${cy}`}>
						{twice((c) => (
							<circle className={`ln${c}`} cx={cx} cy={cy} r="9" pathLength="1" />
						))}
					</g>
				))}
				<rect className="late" x="158" y="178" width="24" height="24" fill="var(--color-red)" />
				{/* span dimension */}
				<g className="late">
					{twice((c) => (
						<path className={`thin${c}`} d="M34 30V48M306 30V48M34 38H306" />
					))}
					<path d="M34 38l8-3v6zM306 38l-8-3v6z" fill="var(--color-ink)" />
					<rect x="128" y="30" width="84" height="16" fill="var(--color-white)" />
					<text className="dim" x="170" y="42" textAnchor="middle">
						{SPECS.span}
					</text>
					<text className="dim" x="170" y="368" textAnchor="middle">
						Plan
					</text>
				</g>
				{/* side view, centre x 500, ground y 300 */}
				{twice((c) => (
					<path className={`ctr${c}`} d="M500 120V320" />
				))}
				{twice((c) => (
					<path className={`ln${c}`} d="M380 300H620" pathLength="1" />
				))}
				{twice((c) => (
					<path className={`ln${c}`} d="M465 218H535M420 212H580M444 196H396M556 196H604" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`ln${c}`} x="465" y="204" width="70" height="26" rx="4" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`ln${c}`} x="414" y="200" width="12" height="14" pathLength="1" />
				))}
				{twice((c) => (
					<rect className={`ln${c}`} x="574" y="200" width="12" height="14" pathLength="1" />
				))}
				{twice((c) => (
					<path
						className={`ln${c}`}
						d="M420 200V196M580 200V196M476 230L452 298M524 230L548 298M444 298H460M540 298H556"
						pathLength="1"
					/>
				))}
				<g className="late">
					{twice((c) => (
						<path className={`thin${c}`} d="M486 230V244M514 230V244" />
					))}
					<rect x="482" y="244" width="36" height="30" fill="var(--color-red)" />
					{/* height dimension */}
					{twice((c) => (
						<path className={`thin${c}`} d="M612 196H640M612 300H640M630 196V300" />
					))}
					<path d="M630 196l-3 8h6zM630 300l-3-8h6z" fill="var(--color-ink)" />
					<text className="dim" transform="translate(648 248) rotate(90)" textAnchor="middle">
						{SPECS.height}
					</text>
					<text className="dim" x="500" y="368" textAnchor="middle">
						Side
					</text>
					{/* callouts, 1 rotor, 2 body, 3 payload, 4 landing legs */}
					{CALLOUTS.map((k) => (
						<g key={k.n}>
							{twice((c) => (
								<path className={`thin${c}`} d={k.line} />
							))}
							<circle cx={k.x} cy={k.y} r="10" fill="var(--color-white)" stroke="var(--color-ink)" />
							<text className="num" x={k.x} y={k.y}>
								{k.n}
							</text>
						</g>
					))}
				</g>
			</svg>
			<figcaption>
				<ol className="m-0 mt-6 grid list-none grid-cols-2 gap-x-8 gap-y-2 p-0 text-[15px] max-[760px]:grid-cols-[minmax(0,1fr)]">
					{LEGEND.map((text, i) => (
						<li key={text} className="flex items-baseline gap-3">
							<b className="tabular-nums">{i + 1}</b>
							<span>{text}</span>
						</li>
					))}
				</ol>
				<p className="m-0 mt-4 text-[14px] leading-5">Vehicle 01. Not to scale. Dimensions to follow.</p>
			</figcaption>
		</figure>
	);
}
