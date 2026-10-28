"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { SignButton } from "@/components/site/SignButton";
import type { SignupFlow } from "./useSignupFlow";

interface Props {
	flow: SignupFlow;
}

const FIELD = "flex flex-1 basis-[200px] flex-col gap-2";
const INPUT = "h-[var(--control-h)] w-full border-0 border-b-[1.5px] border-black bg-transparent p-0 text-[length:var(--control-font)] text-black";

/** Both steps share one slot. The message line is the live region. */
export function AddressForm(props: Props) {
	const flow = props.flow;
	const [address, setAddress] = useState("");
	const [email, setEmail] = useState("");
	const addressRef = useRef<HTMLInputElement>(null);
	const emailRef = useRef<HTMLInputElement>(null);
	const isBusy = flow.status !== "idle";

	useEffect(() => {
		if (flow.step === "email") emailRef.current?.focus();
	}, [flow.step]);

	// "Get updates" links to /#updates: scroll to the form and focus the address field.
	useEffect(() => {
		function focusFromHash() {
			if (window.location.hash !== "#updates") return;
			const input = addressRef.current;
			if (!input) return;
			input.scrollIntoView({ block: "center" });
			input.focus({ preventScroll: true });
		}
		focusFromHash();
		window.addEventListener("hashchange", focusFromHash);
		return () => window.removeEventListener("hashchange", focusFromHash);
	}, []);

	function onFormSubmit(e: FormEvent) {
		e.preventDefault();
		if (flow.step === "address") flow.onCheck(address);
		else if (flow.step === "email") flow.onSubmit(email);
	}

	function onRestartClick() {
		flow.onRestart();
		setAddress("");
		setEmail("");
		// The address row mounts on the next render.
		requestAnimationFrame(() => addressRef.current?.focus());
	}

	return (
		<form id="updates" noValidate onSubmit={onFormSubmit} className="flex flex-col gap-4">
			<div role="status" aria-live="polite" className="flex flex-col gap-4">
				<p className="m-0 text-[18px] font-bold leading-[1.35]">{flow.heading}</p>
				<p className="m-0 min-h-6">{flow.error || flow.hint}</p>
			</div>
			{flow.step === "address" && (
				<div className="flex flex-wrap items-end gap-4">
					<label className={FIELD} htmlFor="address">
						<span className="text-[length:var(--field-label)]">Street address or cross streets</span>
						<input
							id="address"
							ref={addressRef}
							className={INPUT}
							name="address"
							autoComplete="street-address"
							maxLength={200}
							placeholder="NE 45th St and 25th Ave NE"
							value={address}
							onChange={(e) => setAddress(e.target.value)}
						/>
					</label>
					<SignButton label="Check" type="submit" isBusy={isBusy} busyLabel="Checking…" />
				</div>
			)}
			{flow.step === "email" && (
				<>
					<div className="flex flex-wrap items-end gap-4">
						<label className={FIELD} htmlFor="email">
							<span className="text-[length:var(--field-label)]">Email</span>
							<input
								id="email"
								ref={emailRef}
								className={INPUT}
								name="email"
								type="email"
								autoComplete="email"
								placeholder="you@example.com"
								value={email}
								onChange={(e) => setEmail(e.target.value)}
							/>
						</label>
						<SignButton label="Get updates" type="submit" isBusy={isBusy} busyLabel="Sending…" />
					</div>
					<button type="button" className="textbtn" onClick={onRestartClick}>
						Check another address
					</button>
				</>
			)}
			{flow.step === "done" && (
				<button type="button" className="textbtn" onClick={onRestartClick}>
					Check another address
				</button>
			)}
		</form>
	);
}
