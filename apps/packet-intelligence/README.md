# PacketIntelligence

Standalone browser-based drone-delivery research app. Independent of `packet.consumer`; no root configuration or existing app changes required.

## Run

Node.js 22 or newer. No runtime or build dependencies.

```sh
cd apps/packet-intelligence
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
- Install Command: empty; no dependencies

App-local `vercel.json` defines build settings and response headers. Deploy with a separate Vercel project; do not reconfigure another app's project.

## Research and storage

The canvas supports configurable widgets, saved layouts, themes, collapsible navigation, CSV/JSON imports, article cards, and source drilldowns. User-created layouts, imports, notes, and task reviews save in browser storage. Export analysis to back up or move them between browsers/domains. There is no server-side account, shared database, or automatic website/PDF ingestion.

`public/research-data.js` contains the October 25, 2026 research snapshot. It distinguishes reviewed summaries, metadata-indexed pages, linked documents and extraction limitations. Company capabilities and plans are distinct from regulator evidence. IBISWorld figures concern the general US food-delivery industry. The financial workbook and complete licensed PDF are excluded.

Retain source URLs, dates, page references and review status when updating research. Never put credentials or personal notes in the public bundle. This repository and a normal Vercel production deployment are public unless separate access controls are configured.
