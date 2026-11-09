"use client";

import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from "react";
import { SignButton } from "@/components/site/SignButton";
import { scrollPastHero } from "@/lib/scroll";
import { TextField } from "./TextField";
import type { SignupFlow } from "./useSignupFlow";

const MSG_ID = "updates-msg";

interface Props {
	flow: SignupFlow;
}

/** Both steps share one slot. The message line is the live region. */
export function AddressForm(props: Props) {
	const flow = props.flow;
	const [address, setAddress] = useState("");
	const [email, setEmail] = useState("");
	const addressRef = useRef<HTMLInputElement>(null);
	const emailRef = useRef<HTMLInputElement>(null);
	const isBusy = flow.status !== "idle";
	const hasError = flow.error !== "";

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

	function onLearnMoreClick(e: MouseEvent<HTMLAnchorElement>) {
		if (scrollPastHero()) e.preventDefault();
	}

	function onRestartClick() {
		flow.onRestart();
		setAddress("");
		setEmail("");
		// The address row mounts on the next render.
		requestAnimationFrame(() => addressRef.current?.focus());
	}

	const msg = (
		<p id={MSG_ID} role="status" aria-live="polite" className={`m-0 min-h-6${hasError ? " text-red" : ""}`}>
			{flow.error || flow.hint}
		</p>
	);

	return (
		<form id="updates" noValidate onSubmit={onFormSubmit} className="flex flex-col gap-4">
			<p role="status" aria-live="polite" className="m-0 text-[24px] font-bold leading-[1.3]">
				{flow.heading}
			</p>
			{flow.step === "address" && (
				<>
				<div className="flex flex-wrap items-end gap-4 max-[760px]:flex-col max-[760px]:items-start">
					<TextField
						id="address"
						label="Street address or cross streets"
						isLabelHidden
						inputRef={addressRef}
						name="address"
						autoComplete="street-address"
						maxLength={200}
						isInvalid={hasError}
						describedBy={MSG_ID}
						placeholder="NE 45th St and 25th Ave NE"
						value={address}
						onChange={(e) => setAddress(e.target.value)}
					/>
					<SignButton label="Check" type="submit" isBusy={isBusy} busyLabel="Checking…" />
				</div>
				{msg}
				</>
			)}
			{flow.step === "email" && (
				<>
					<div className="flex flex-wrap items-end gap-4 max-[760px]:flex-col max-[760px]:items-start">
						<TextField
							id="email"
							label="Email"
							inputRef={emailRef}
							name="email"
							type="email"
							autoComplete="email"
							placeholder="you@example.com"
							isInvalid={hasError}
							describedBy={MSG_ID}
							value={email}
							onChange={(e) => setEmail(e.target.value)}
						/>
						<SignButton label="Get updates" type="submit" isBusy={isBusy} busyLabel="Sending…" />
					</div>
					{msg}
					<button type="button" className="textbtn" onClick={onRestartClick}>
						Check another address
					</button>
				</>
			)}
			{flow.step === "done" && (
				<>
					{/* Signed up: point the way down the page, so the hero is not a dead end. */}
					<a className="textlink self-start" href="#get-h" onClick={onLearnMoreClick}>
						<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
							<path d="M10 2v15M4 11l6 6 6-6" />
						</svg>
						See what Packet brings
					</a>
					<button type="button" className="textbtn" onClick={onRestartClick}>
						Check another address
					</button>
				</>
			)}
		</form>
	);
}
