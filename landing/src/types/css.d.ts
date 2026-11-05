import "react";

declare module "react" {
	interface CSSProperties {
		/** Extra screen heights a pinned section holds for. Read by `.pin` in globals.css. */
		"--pin-length"?: number;
		/** Progress through a pinned section, 0 to 1. Read by the ramps in globals.css. */
		"--p"?: number;
	}
}
