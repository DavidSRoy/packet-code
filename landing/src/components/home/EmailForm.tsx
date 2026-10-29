"use client";

import { useState, type FormEvent } from "react";
import { SignButton } from "@/components/site/SignButton";
import { TextField } from "./TextField";
import { useEmailSignup } from "./useEmailSignup";

const MSG_ID = "updates-2-msg";

export function EmailForm() {
	const signup = useEmailSignup();
	const [email, setEmail] = useState("");

	function onFormSubmit(e: FormEvent) {
		e.preventDefault();
		signup.onSubmit(email);
	}

	return (
		<>
			<form id="updates-2" noValidate onSubmit={onFormSubmit} className="flex flex-wrap items-end gap-4">
				<TextField
					id="email-2"
					label="Email"
					name="email"
					type="email"
					autoComplete="email"
					placeholder="you@example.com"
					isInvalid={signup.isError}
					describedBy={MSG_ID}
					value={email}
					onChange={(e) => setEmail(e.target.value)}
				/>
				<SignButton label="Get updates" type="submit" isBusy={signup.status === "sending"} busyLabel="Sending…" />
			</form>
			<p id={MSG_ID} role="status" aria-live="polite" className="m-0 min-h-6 text-[14px]">
				{signup.message}
			</p>
		</>
	);
}
