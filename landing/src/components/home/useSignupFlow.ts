"use client";

import { useCallback, useRef, useState } from "react";
import { U_VILLAGE } from "@/config/service-area";
import { distanceKm, type LatLng } from "@/lib/geo";
import { submitSignup } from "@/lib/attribution";

export type Step = "address" | "email" | "done";
export type Status = "idle" | "checking" | "sending";

/** Beyond this the baked street disc ends and the globe would aim at blank dots (ruling R8). */
const AIM_RADIUS_KM = 2.5;

const ASK = "Is Packet coming to your street?";
const FAILED = "Something went wrong. Try again in a moment.";
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type CheckResult =
	| { kind: "not_found" }
	| { kind: "found"; isInArea: boolean; point: LatLng }
	| { kind: "error" };

function isRecord(v: unknown): v is Record<string, unknown> {
	return typeof v === "object" && v !== null;
}

async function checkAddress(q: string): Promise<CheckResult> {
	try {
		const res = await fetch("/api/check", {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ q }),
		});
		if (!res.ok) return { kind: "error" };
		const json: unknown = await res.json();
		if (!isRecord(json)) return { kind: "error" };
		if (json.found === false) return { kind: "not_found" };
		if (json.found === true && typeof json.inArea === "boolean" && typeof json.lat === "number" && typeof json.lng === "number") {
			return { kind: "found", isInArea: json.inArea, point: [json.lat, json.lng] };
		}
		return { kind: "error" };
	} catch (err) {
		console.error("[Hero:checkAddress] Request failed —", { name: err instanceof Error ? err.name : "unknown" });
		return { kind: "error" };
	}
}

export interface SignupFlow {
	step: Step;
	status: Status;
	heading: string;
	hint: string;
	error: string;
	target: LatLng | null;
	onCheck(q: string): void;
	onSubmit(email: string): void;
	onRestart(): void;
}

export function useSignupFlow(): SignupFlow {
	const [step, setStep] = useState<Step>("address");
	const [status, setStatus] = useState<Status>("idle");
	const [heading, setHeading] = useState(ASK);
	const [hint, setHint] = useState("");
	const [error, setError] = useState("");
	const [target, setTarget] = useState<LatLng | null>(null);
	// A ref guards the in-flight window; state would lag behind a fast double click.
	const isBusyRef = useRef(false);
	const checkedQRef = useRef<string | null>(null);

	const onCheck = useCallback((q: string) => {
		if (isBusyRef.current) return;
		const trimmed = q.trim();
		if (!trimmed) {
			setError("Enter a street address or cross streets.");
			return;
		}
		isBusyRef.current = true;
		setStatus("checking");
		setError("");
		void checkAddress(trimmed).then((r) => {
			isBusyRef.current = false;
			setStatus("idle");
			if (r.kind === "error") {
				setError(FAILED);
			} else if (r.kind === "not_found") {
				setError("We couldn't find that address. Try cross streets, like NE 45th St and 25th Ave NE.");
			} else {
				checkedQRef.current = trimmed;
				setTarget(distanceKm(r.point, U_VILLAGE) <= AIM_RADIUS_KM ? r.point : null);
				setHeading(r.isInArea ? "That's inside the first area around U Village." : "That's outside the first area, for now.");
				setHint(r.isInArea ? "Get an email when Packet launches." : "Get an email when Packet reaches your street.");
				setStep("email");
			}
		});
	}, []);

	const onSubmit = useCallback((email: string) => {
		if (isBusyRef.current) return;
		const trimmed = email.trim();
		if (!EMAIL_SHAPE.test(trimmed)) {
			setError("Enter an email address, like you@example.com.");
			return;
		}
		isBusyRef.current = true;
		setStatus("sending");
		setError("");
		void submitSignup(trimmed, checkedQRef.current).then((r) => {
			isBusyRef.current = false;
			setStatus("idle");
			if (r === "ok") {
				setHeading("You're on the list.");
				setHint("");
				setStep("done");
			} else {
				setError(r === "invalid_email" ? "Enter an email address, like you@example.com." : FAILED);
			}
		});
	}, []);

	const onRestart = useCallback(() => {
		if (isBusyRef.current) return;
		checkedQRef.current = null;
		setStep("address");
		setHeading(ASK);
		setHint("");
		setError("");
		setTarget(null);
	}, []);

	return { step, status, heading, hint, error, target, onCheck, onSubmit, onRestart };
}
