export interface SpecRow {
	key: string;
	value: string;
}

interface Props {
	rows: readonly SpecRow[];
}

export function SpecList(props: Props) {
	return (
		<dl className="m-0 mt-2 border-t border-ink">
			{props.rows.map((row) => (
				<div
					key={row.key}
					className="grid grid-cols-[minmax(0,160px)_minmax(0,1fr)] gap-4 border-b border-ink py-2.5 max-[760px]:grid-cols-[minmax(0,120px)_minmax(0,1fr)]"
				>
					<dt className="pt-0.5 font-label text-[13px] font-semibold uppercase tracking-[0.08em]">{row.key}</dt>
					<dd className="m-0 text-[15px]">{row.value}</dd>
				</div>
			))}
		</dl>
	);
}
