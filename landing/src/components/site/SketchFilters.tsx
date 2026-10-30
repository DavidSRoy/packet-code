export function SketchFilters() {
	return (
		<svg aria-hidden="true" width="0" height="0" style={{ position: "absolute" }}>
			<defs>
				<filter id="pen1" filterUnits="userSpaceOnUse" x="-20" y="-20" width="700" height="420">
					<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="4" />
					<feDisplacementMap in="SourceGraphic" scale="4" />
				</filter>
				<filter id="pen2" filterUnits="userSpaceOnUse" x="-20" y="-20" width="700" height="420">
					<feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" seed="11" />
					<feDisplacementMap in="SourceGraphic" scale="5" />
				</filter>
				<filter id="pen3" filterUnits="userSpaceOnUse" x="-20" y="-20" width="700" height="420">
					<feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="7" />
					<feDisplacementMap in="SourceGraphic" scale="1.8" />
				</filter>
			</defs>
		</svg>
	);
}
