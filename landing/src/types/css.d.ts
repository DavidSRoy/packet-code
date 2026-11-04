import "react";

declare module "react" {
	interface CSSProperties {
		/** Extra screen heights a pinned section holds for. Read by `.pin` in globals.css. */
		"--pin-length"?: number;
	}
}
