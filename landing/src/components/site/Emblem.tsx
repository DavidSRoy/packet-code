interface Props {
	size: number;
}

interface Mark {
	key: string;
	style: React.CSSProperties;
}

const LONG = ".296em";
const THIN = ".046em";
const OFF = "-.407em";

const MARKS: readonly Mark[] = [
	{ key: "tl-h", style: { top: 0, left: OFF, width: LONG, height: THIN } },
	{ key: "tl-v", style: { left: 0, top: OFF, width: THIN, height: LONG } },
	{ key: "tr-h", style: { top: 0, right: OFF, width: LONG, height: THIN } },
	{ key: "tr-v", style: { right: 0, top: OFF, width: THIN, height: LONG } },
	{ key: "bl-h", style: { bottom: 0, left: OFF, width: LONG, height: THIN } },
	{ key: "bl-v", style: { left: 0, bottom: OFF, width: THIN, height: LONG } },
	{ key: "br-h", style: { bottom: 0, right: OFF, width: LONG, height: THIN } },
	{ key: "br-v", style: { right: 0, bottom: OFF, width: THIN, height: LONG } },
];

export function Emblem(props: Props) {
	return (
		<span className="emblem" role="img" aria-label="Packet" style={{ fontSize: props.size }}>
			<span aria-hidden="true">Packet</span>
			{MARKS.map((mark) => (
				<i key={mark.key} aria-hidden="true" style={mark.style} />
			))}
		</span>
	);
}
