interface Props {
	no: string;
	title: string;
	children: React.ReactNode;
}

export function ManualSection(props: Props) {
	const headingId = `manual-${props.no.replace(".", "-")}-h`;
	return (
		<section
			aria-labelledby={headingId}
			className="grid grid-cols-[minmax(0,1fr)_minmax(0,11fr)] gap-6 border-t-[1.5px] border-ink pb-4 pt-6 max-[760px]:grid-cols-[minmax(0,1fr)] max-[760px]:gap-2"
		>
			<span className="lbl pt-2.5 text-[15px] max-[760px]:pt-0">{props.no}</span>
			<div className="flex max-w-[960px] flex-col gap-6">
				<h2
					id={headingId}
					className="m-0 max-w-[20ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
				>
					{props.title}
				</h2>
				{props.children}
			</div>
		</section>
	);
}
