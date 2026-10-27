# PacketIntelligence

Standalone browser-based drone-delivery research app. Independent of `packet.consumer`; no root configuration or existing app changes required.

## Run

Node.js 22 or newer. Run `npm ci` to install the Vercel middleware helper.

```sh
cd apps/packet-intelligence
npm ci
npm test
npm run build
npm run dev
```

Development: `http://127.0.0.1:4173`. Build output: `dist/`.

## Vercel project settings

- Repository: `DavidSRoy/packet-code`
- Root Directory: `apps/packet-intelligence`
- Framework: Other
- Build Command: `node scripts/build.mjs`
- Output Directory: `dist`
- Install Command: `npm ci`

App-local `vercel.json` defines build settings and response headers. Deploy with a separate Vercel project; do not reconfigure another app's project.

## Research and storage

The canvas supports configurable widgets, saved layouts, themes, collapsible navigation, CSV/JSON imports, article cards, and source drilldowns. User-created layouts, imports, notes, and task reviews save in browser storage. Export analysis to back up or move them between browsers/domains. A shared server-enforced test login protects access; research edits remain browser-local. There is no shared database or automatic website/PDF ingestion.

`public/research-data.js` contains the October 25, 2026 research snapshot. It distinguishes reviewed summaries, metadata-indexed pages, linked documents and extraction limitations. Company capabilities and plans are distinct from regulator evidence. IBISWorld figures concern the general US food-delivery industry. The financial workbook is excluded. The original IBISWorld PDF is included under `public/documents/` with the user’s explicit authorization.

Retain source URLs, dates, page references and review status when updating research. Never put credentials or personal notes in the public bundle. The GitHub fork is public. Vercel production is protected by the test-login middleware.

## Object platform

The Ontology view separates source collections, typed objects and the analytical layer. Explicit, evidence-labeled links support object traversal and creating a linked object set for charting. `ontology.js` defines object properties, transformations and relationship resolution. Unknown ownership or tenant counts stay null / unverified.

Seattle's official SDCI snapshot contains the latest 500 permit descriptions matching RESTAURANT. Permits link to normalized site addresses; a permit is not proof of a current restaurant. Company-page portfolio prospects remain separately labeled. King County parcel ownership is not yet joined and its food-establishment API required authentication when checked. This is a browser-local object model, not a server ingestion service or a Palantir deployment.

Refresh the public Seattle snapshot explicitly with `node scripts/refresh-seattle.mjs`, review source dates and changes, then run tests/build. Original URL: https://data.seattle.gov/Built-Environment/Building-Permits/76t5-zqzr

## Test login

Vercel middleware protects every route, including static research datasets and PDFs. Required sensitive environment variables: `PACKET_TEST_USER`, `PACKET_TEST_PASSWORD_HASH` (`salt:PBKDF2-SHA256 hex`, 150,000 iterations), and `PACKET_SESSION_SECRET` (at least 32 random characters). No password or signing secret is bundled in the browser. Sessions use signed eight-hour Secure/HttpOnly/SameSite cookies; logout deletes the session cookie. Rotate the signing secret to invalidate all sessions. Login attempts have a best-effort per-instance limit, not a distributed account lockout.

Run `npm test` for research and auth checks. The Python static preview intentionally does not run server authentication; use Vercel for the protected application. This shared demo account is temporary, not a replacement for individual-user identity management. Files previously published to the public GitHub fork remain publicly available there; this login protects the Vercel site only.
