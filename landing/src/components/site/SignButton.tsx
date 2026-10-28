interface Props {
	label: string;
	type?: "submit" | "button";
	isBusy?: boolean;
	busyLabel?: string;
	onClick?: () => void;
}

export function SignButton(props: Props) {
	const isBusy = props.isBusy === true;
	const text = isBusy && props.busyLabel ? props.busyLabel : props.label;
	return (
		<button
			className="sign"
			type={props.type ?? "button"}
			disabled={isBusy}
			aria-disabled={isBusy}
			onClick={props.onClick}
		>
			<span className="arrow" aria-hidden="true">
				<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5">
					<path d="M2 10h15M11 4l6 6-6 6" />
				</svg>
			</span>
			<span className="txt">{text}</span>
		</button>
	);
}
