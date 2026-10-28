import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
	...nextVitals,
	...nextTs,
	globalIgnores([".next/**", ".open-next/**", "node_modules/**", "cloudflare-env.d.ts", "next-env.d.ts"]),
]);
