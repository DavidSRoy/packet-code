import type { ComponentPropsWithoutRef, Ref } from "react";

interface Props extends Omit<ComponentPropsWithoutRef<"input">, "id" | "className"> {
	id: string;
	label: string;
	inputRef?: Ref<HTMLInputElement>;
	/** True while an error message for this field is showing. */
	isInvalid?: boolean;
	/** Id of the message line that describes this field. */
	describedBy?: string;
}

const INPUT = "h-[var(--control-h)] w-full border-0 border-b-[1.5px] border-ink bg-transparent p-0 text-[length:var(--control-font)] text-ink";

/** Label above an underlined input: the field used by the hero and the closing sign-up. */
export function TextField(props: Props) {
	const { id, label, inputRef, isInvalid, describedBy, ...rest } = props;
	return (
		<label className="flex flex-1 basis-[200px] flex-col gap-2" htmlFor={id}>
			<span className="lbl text-[length:var(--field-label)]">{label}</span>
			<input
				id={id}
				ref={inputRef}
				className={INPUT}
				aria-invalid={isInvalid || undefined}
				aria-describedby={describedBy}
				{...rest}
			/>
		</label>
	);
}
