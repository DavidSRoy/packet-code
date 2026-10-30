"use client";

import { useEffect } from "react";
import { captureAttribution } from "@/lib/attribution";

/** Stores UTM tags and the referrer from whichever page the visitor lands on. */
export function AttributionCapture() {
	useEffect(() => {
		captureAttribution();
	}, []);
	return null;
}
