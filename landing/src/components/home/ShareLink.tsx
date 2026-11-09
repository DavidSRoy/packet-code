"use client";

import { useState } from "react";

const TITLE = "Packet";
const TEXT = "Autonomous delivery from U Village shops. Check if Packet reaches your street.";

/** Opens the phone's share sheet where there is one, otherwise copies the page's link. */
export function ShareLink() {
	const [note, setNote] = useState("");

	async function onShareClick() {
		const url = `${window.location.origin}/`;
		if (typeof navigator.share === "function") {
			try {
				await navigator.share({ title: TITLE, text: TEXT, url });
				return;
			} catch (err) {
				// The person closed the sheet: nothing to do.
				if (err instanceof DOMException && err.name === "AbortError") return;
			}
		}
		try {
			await navigator.clipboard.writeText(url);
			setNote("Link copied.");
		} catch {
			setNote(`Copy this link: ${url}`);
		}
	}

	return (
		<>
			<button type="button" className="textlink cursor-pointer border-0 bg-transparent p-0 font-[inherit] text-[length:inherit]" onClick={onShareClick}>
				Share the link
			</button>
			<span role="status" aria-live="polite" className="ml-2 text-[14px]">
				{note}
			</span>
		</>
	);
}
