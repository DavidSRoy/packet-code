# packet-code

Monorepo for Team DroneTask. Two projects live here:

- `landing/` — the marketing site. Next.js 16 on Cloudflare Workers via OpenNext, with a D1 database (`DB`) for sign-ups.
- `packet.consumer/` — the SwiftUI customer app (Xcode project).

## Landing site

All commands run from `landing/`.

```bash
npm ci                    # install (keep package-lock.json tab-indented; don't commit an npm-reformatted lockfile)
npm run dev:local         # apply D1 migrations to the local DB, then start next dev on :3000
npm test                  # node --test, no build needed
npm run lint
npx tsc --noEmit
npx opennextjs-cloudflare build   # production Workers bundle into .open-next/
npm run check:placeholders        # lists [UPPERCASE] copy placeholders still in src/
```

- `next dev` uses Wrangler's local bindings (`initOpenNextCloudflareForDev`), so `/api/signup` writes to the local D1 under `.wrangler/state`. Run `npm run db:migrate:local` once per fresh checkout or the `signups` table won't exist.
- Inspect local sign-ups: `npx wrangler d1 execute packet-landing --local --command "select * from signups"`.
- `/api/check` and `/api/signup` call the Nominatim geocoder (nominatim.openstreetmap.org).
- `wrangler.jsonc` still has a placeholder D1 `database_id`; replace it with the real id before deploying.
- Pages: `/`, `/products`, `/press`, `/privacy`.
- Deploys go through Cloudflare Workers Builds (see `landing/README.md`), not GitHub Actions.
