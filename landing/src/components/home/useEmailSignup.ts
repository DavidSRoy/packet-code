"use client";

import { useCallback, useRef, useState } from "react";
import { submitSignup } from "@/lib/attribution";

export type EmailStatus = "idle" | "sending" | "done";

const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const INVALID = "Enter an email address, like you@example.com.";
const FAILED = "Something went wrong. Try again in a moment.";

export interface EmailSignup {
	status: EmailStatus;
	message: string;
	/** True while the message is an error rather than the confirmation. */
	isError: boolean;
	onSubmit(email: string): void;
}

/** Email-only sign-up: no address step, so the row's in_area stays null. */
export function useEmailSignup(): EmailSignup {
	const [status, setStatus] = useState<EmailStatus>("idle");
	const [message, setMessage] = useState("");
	const isBusyRef = useRef(false);

	const onSubmit = useCallback((email: string) => {
		if (isBusyRef.current) return;
		const trimmed = email.trim();
		if (!EMAIL_SHAPE.test(trimmed)) {
			setMessage(INVALID);
			return;
		}
		isBusyRef.current = true;
		setStatus("sending");
		setMessage("");
		void submitSignup(trimmed, null).then((r) => {
			isBusyRef.current = false;
			if (r === "ok") {
				setStatus("done");
				setMessage("You're on the list.");
			} else {
				setStatus("idle");
				setMessage(r === "invalid_email" ? INVALID : FAILED);
			}
		});
	}, []);

	return { status, message, isError: message !== "" && status !== "done", onSubmit };
}
