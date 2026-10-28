const KEY = "packet:attr";

export interface Attribution {
	utm_source?: string;
	utm_medium?: string;
	utm_campaign?: string;
	referrer?: string;
}

const FIELDS = ["utm_source", "utm_medium", "utm_campaign"] as const;

function isStringRecord(v: unknown): v is Record<string, unknown> {
	return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function readAttribution(): Attribution {
	try {
		const raw = window.sessionStorage.getItem(KEY);
		if (!raw) return {};
		const parsed: unknown = JSON.parse(raw);
		if (!isStringRecord(parsed)) return {};
		const out: Attribution = {};
		for (const k of [...FIELDS, "referrer"] as const) {
			const v = parsed[k];
			if (typeof v === "string" && v) out[k] = v;
		}
		return out;
	} catch {
		return {};
	}
}

/** First load only: stores utm_* and the referrer, never overwriting a stored value. */
export function captureAttribution(): void {
	try {
		const next: Attribution = readAttribution();
		const params = new URLSearchParams(window.location.search);
		for (const k of FIELDS) {
			const v = params.get(k);
			if (v && !next[k]) next[k] = v;
		}
		if (document.referrer && !next.referrer) next.referrer = document.referrer;
		window.sessionStorage.setItem(KEY, JSON.stringify(next));
	} catch {
		// Storage can be blocked; attribution is best effort.
	}
}

export async function submitSignup(email: string, q: string | null): Promise<"ok" | "invalid_email" | "error"> {
	try {
		const body = { email, ...(q ? { q } : {}), ...readAttribution() };
		const res = await fetch("/api/signup", {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify(body),
		});
		if (res.ok) return "ok";
		if (res.status === 400) {
			const json: unknown = await res.json().catch(() => null);
			if (isStringRecord(json) && json.error === "invalid_email") return "invalid_email";
		}
		return "error";
	} catch (err) {
		console.error("[Attribution:submitSignup] Request failed —", { name: err instanceof Error ? err.name : "unknown" });
		return "error";
	}
}
