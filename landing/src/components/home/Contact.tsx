"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { SignButton } from "@/components/site/SignButton";
import { submitContact, type ContactResult } from "@/lib/attribution";
import { isContactTopic, MAX_MESSAGE, type ContactTopic } from "@/lib/contact-input";
import { TextField } from "./TextField";

const TOPICS: readonly { value: ContactTopic; label: string }[] = [
	{ value: "shop", label: "A shop or restaurant" },
	{ value: "building", label: "A building or campus" },
	{ value: "press", label: "Press" },
	{ value: "other", label: "Something else" },
];

const MSG_ID = "contact-msg-line";
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const ERRORS: Record<Exclude<ContactResult, "ok">, string> = {
	invalid_name: "Enter your name.",
	invalid_email: "Enter an email address, like you@example.com.",
	invalid_message: `Keep the message under ${MAX_MESSAGE} characters.`,
	error: "Something went wrong. Try again in a moment.",
};

const MESSAGE_INPUT =
	"min-h-[96px] w-full resize-y border-0 border-b-[1.5px] border-ink bg-transparent p-0 py-2 text-[length:var(--control-font)] text-ink";

/**
 * Contact for anyone: shops, buildings, press or anything else. Links can preselect the topic with
 * /?topic=press#contact. The hidden "website" field catches bots; people never see it.
 */
export function Contact() {
	const [topic, setTopic] = useState<ContactTopic>("shop");
	const [name, setName] = useState("");
	const [email, setEmail] = useState("");
	const [org, setOrg] = useState("");
	const [message, setMessage] = useState("");
	const [website, setWebsite] = useState("");
	const [status, setStatus] = useState<"idle" | "sending" | "done">("idle");
	const [line, setLine] = useState("");
	const [invalid, setInvalid] = useState<"name" | "email" | "message" | null>(null);
	const isBusyRef = useRef(false);
	const nameRef = useRef<HTMLInputElement>(null);

	// A link like /?topic=press#contact picks the topic and puts the cursor in the first field.
	useEffect(() => {
		function fromUrl() {
			const wanted = new URLSearchParams(window.location.search).get("topic");
			if (isContactTopic(wanted)) setTopic(wanted);
			if (window.location.hash === "#contact") nameRef.current?.focus({ preventScroll: true });
		}
		fromUrl();
		window.addEventListener("hashchange", fromUrl);
		return () => window.removeEventListener("hashchange", fromUrl);
	}, []);

	function onFormSubmit(e: FormEvent) {
		e.preventDefault();
		if (isBusyRef.current) return;
		if (name.trim() === "") {
			setInvalid("name");
			setLine(ERRORS.invalid_name);
			return;
		}
		if (!EMAIL_SHAPE.test(email.trim())) {
			setInvalid("email");
			setLine(ERRORS.invalid_email);
			return;
		}
		isBusyRef.current = true;
		setStatus("sending");
		setInvalid(null);
		setLine("");
		void submitContact({ topic, name, email, org, message, website }).then((r) => {
			isBusyRef.current = false;
			if (r === "ok") {
				setStatus("done");
				setLine(`Thanks, ${name.trim().split(/\s+/)[0]}. We will write back to ${email.trim()}.`);
				setName("");
				setEmail("");
				setOrg("");
				setMessage("");
				return;
			}
			setStatus("idle");
			setInvalid(r === "invalid_name" ? "name" : r === "invalid_email" ? "email" : r === "invalid_message" ? "message" : null);
			setLine(ERRORS[r]);
		});
	}

	const isError = line !== "" && status !== "done";

	return (
		<section id="contact" aria-labelledby="contact-h" className="pad scroll-mt-16 py-section">
			<div className="grid grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-16 border-t-[8px] border-ink pt-12 max-[900px]:grid-cols-1 max-[900px]:gap-10">
				<div className="flex flex-col gap-5">
					<span className="lbl">Contact</span>
					<h2
						id="contact-h"
						className="m-0 max-w-[16ch] text-balance font-display text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.12]"
					>
						Get in touch.
					</h2>
					<p className="m-0 max-w-[40ch] text-[20px] leading-[1.45]">
						Run a shop, manage a building, or just curious? Packet starts around University Village, and we want
						to hear from the people and places nearby.
					</p>
				</div>
				<form noValidate onSubmit={onFormSubmit} className="flex flex-col gap-7 self-end">
					<fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
						<legend className="lbl mb-3 p-0 text-[length:var(--field-label)]">This is about</legend>
						<div className="flex flex-wrap gap-2">
							{TOPICS.map((t) => (
								<label
									key={t.value}
									className="cursor-pointer border-[1.5px] border-ink px-3 py-2 text-[15px] has-[:checked]:bg-ink has-[:checked]:text-white has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2"
								>
									<input
										type="radio"
										name="topic"
										value={t.value}
										checked={topic === t.value}
										onChange={() => setTopic(t.value)}
										className="sr-only"
									/>
									{t.label}
								</label>
							))}
						</div>
					</fieldset>
					<div className="flex flex-wrap gap-6 max-[760px]:flex-col">
						<TextField
							id="contact-name"
							inputRef={nameRef}
							label="Your name"
							name="name"
							autoComplete="name"
							placeholder="First and last"
							maxLength={200}
							isInvalid={invalid === "name"}
							describedBy={MSG_ID}
							value={name}
							onChange={(e) => setName(e.target.value)}
						/>
						<TextField
							id="contact-email"
							label="Email"
							name="email"
							type="email"
							autoComplete="email"
							placeholder="you@example.com"
							maxLength={254}
							isInvalid={invalid === "email"}
							describedBy={MSG_ID}
							value={email}
							onChange={(e) => setEmail(e.target.value)}
						/>
					</div>
					<div className="flex">
						<TextField
							id="contact-org"
							label="Shop, building or company (optional)"
							name="org"
							autoComplete="organization"
							placeholder="Where you are"
							maxLength={200}
							value={org}
							onChange={(e) => setOrg(e.target.value)}
						/>
					</div>
					<label className="flex flex-col gap-2" htmlFor="contact-message">
						<span className="lbl text-[length:var(--field-label)]">Message (optional)</span>
						<textarea
							id="contact-message"
							name="message"
							rows={3}
							maxLength={MAX_MESSAGE}
							placeholder="What you have in mind"
							className={MESSAGE_INPUT}
							aria-invalid={invalid === "message" || undefined}
							aria-describedby={MSG_ID}
							value={message}
							onChange={(e) => setMessage(e.target.value)}
						/>
					</label>
					<div className="absolute left-[-9999px] h-px w-px overflow-hidden" aria-hidden="true">
						<label htmlFor="contact-website">Website</label>
						<input
							id="contact-website"
							name="website"
							tabIndex={-1}
							autoComplete="off"
							value={website}
							onChange={(e) => setWebsite(e.target.value)}
						/>
					</div>
					<div className="flex flex-wrap items-center gap-x-6 gap-y-3">
						<SignButton label="Send" type="submit" isBusy={status === "sending"} busyLabel="Sending…" />
						<p className="m-0 text-[14px]">
							We only use this to reply to you. <a href="/privacy#contact-h">Privacy</a>
						</p>
					</div>
					<p id={MSG_ID} role="status" aria-live="polite" className={`m-0 min-h-6 text-[15px]${isError ? " text-red" : ""}`}>
						{line}
					</p>
				</form>
			</div>
		</section>
	);
}
