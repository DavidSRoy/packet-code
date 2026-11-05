# Packet Landing Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Packet marketing site (landing, Products, Press, Privacy) with an address-based service-area check and a D1-backed sign-up list, deployed as the existing `landing` Cloudflare Worker.

**Architecture:**
- **Pages:** Next 16 App Router pages under `landing/src/app`, statically rendered. The interactive pieces (globe, route trip, tunnel, showcase, forms) are client components.
- **API:** two route handlers, `/api/check` and `/api/signup`, run on the Worker. They share a pure, dependency-injected core (service area, geocoder, input parsing), so it can be tested with `node --test` and no network.
- **Storage:** one D1 table holds sign-ups.

**Tech Stack:** Next 16.4, React 19, Tailwind 4, `@opennextjs/cloudflare` 1.20, Wrangler 4, D1, Nominatim (OpenStreetMap). Node 24 runs the tests: `node --test` with native TypeScript stripping, so no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-26-packet-landing-design.md`. Visual reference: `docs/superpowers/specs/2026-10-26-packet-landing/mockup.html` and its PNGs. Section numbers below (§n) refer to the spec.

## Global Constraints

- **Where the code lives:** all code goes in `landing/`. Package manager **npm**. **No new dependencies.** Ask Tanner before adding any.
- **Branch:** `feat/landing-site`, cut from `feat/landing-opennext`, in a fresh worktree. `feat/landing-opennext` is already checked out in another worktree, so don't use it. PR into `master`, opened as a draft in Task 0.
- **Merging `master` deploys production** (Workers Builds). Never merge. The PR stays a draft until Tanner supplies the D1 `database_id` and the analytics token.
- **TypeScript:** strict. No `any`, no `as` casts, no `@ts-ignore`.
- **React:** one component per file, `PascalCase.tsx`, a named `Props` interface above each component, `props.x` access, `is`/`has` boolean names, `on`-prefixed handlers. Complex state goes in a colocated `useX.ts` hook.
- **Errors:** log as `[Module:Function] Description — {context}`. Never log email or address text.
- **Copy:** exactly as the spec writes it. No em dashes in user-facing text. No "seamless", "magic", "revolutionary" or "intelligent". Public pages never mention CSE 589, a university, a class or a team name.
- **Inks:** `#B4432F` red, `#111111` black, `#D3A13F` mustard, `#FFFFFF` white, plus `#d9d9d9` for the progress track only.
- **Type:**
  - Libre Franklin 400/600 for headings, nav and footer links;
  - Atkinson Hyperlegible Next 400/700 for body and controls;
  - Barlow Condensed 600 uppercase for labels.
  - IBM Plex Mono is never used.
- **Layout and controls:** side margin `clamp(20px,6.5vw,96px)` plus safe-area insets. Controls 44px tall with 16px text. Field labels 12px.
- **Repetition limits:** one station-sign button per screen, one mustard tag per screen, leading lines once.
- **Reduced motion:** every animation has a `prefers-reduced-motion: reduce` path that shows the final state with nothing moving. Canvases stop animating when off screen or when `document.hidden`.
- **Verification:** verify on `npm run build` plus `npm run preview` (the Cloudflare runtime) with local D1, never on `next dev`. Port 3000 is Tanner's; preview on another port.
- **Remote resources are Tanner's:** `wrangler d1 create` and remote migrations are his. Use `--local` only.

## Review Focus

1. **Geocoder slow, down or rate-limited.** Nominatim times out after 4s or returns 5xx or 429. Expected: the form shows "Something went wrong. Try again in a moment.", the address stays in the field, and the button re-enables. Covered by tests in Task 2 and the browser check in Task 6.
2. **Ambiguous or out-of-town address** (for example "Main St", "Portland"). Expected: not-found, never a far-away point counted as outside. The geocoder URL must be `bounded=1` to the Seattle box. Tested in Task 2.
3. **The same person signing up twice with different casing or spacing** (" Ana@Example.com "). Expected: one row, the email lowercased and trimmed, `created_at` kept. Tested in Tasks 1 and 3.
4. **Double-clicks and rapid resubmits.** Expected: one request in flight, and the button disabled with "Checking…" or "Sending…". Checked in the browser in Task 6.
5. **Showcase while the tab is hidden or the user prefers reduced motion.** Expected: no auto-advance, so returning users don't find the showcase silently moved on. Checked in Task 10.

## File map (all under `landing/`)

| File | Responsibility |
|---|---|
| `src/config/service-area.ts` | Boundary polygon, U Village center, Seattle geocoder box |
| `src/lib/geo.ts` | `pointInPolygon`, `round` |
| `src/lib/signup-input.ts` | Parse and validate API bodies |
| `src/server/geocode.ts` | Nominatim call |
| `src/server/check-address.ts` | Geocode plus inside test |
| `src/server/signups.ts` | D1 upsert |
| `src/server/handlers.ts` | Framework-free request handlers (testable) |
| `src/app/api/check/route.ts`, `src/app/api/signup/route.ts` | Thin Next wrappers |
| `migrations/0001_signups.sql` | Table |
| `test/*.test.ts` | `node --test` suites |
| `src/app/layout.tsx`, `src/app/globals.css` | Fonts, tokens, shell, analytics beacon |
| `src/components/site/*` | `Nav`, `Footer`, `Emblem`, `SignButton`, `LeadingLines`, `SketchFilters` |
| `src/components/drawings/*` | Sketched SVG drawings |
| `src/lib/canvas/*` | Shared canvas helpers (loop, halftone sphere, marks) |
| `src/lib/attribution.ts` | UTM and referrer capture in `sessionStorage` |
| `src/components/home/*` | Landing sections and their hooks |
| `src/data/*` | `products.ts`, `store-items.ts`, `news.ts`, `streets.json` |
| `src/app/products/page.tsx`, `src/app/press/page.tsx`, `src/app/privacy/page.tsx` | Subpages |
| `scripts/fetch-streets.mjs`, `scripts/check-placeholders.mjs` | One-off and pre-launch scripts |

---

### Task 0: Branch, worktree, draft PR

**Files:** `docs/superpowers/specs/*` and `docs/superpowers/plans/*`, copied from branch `tannerpham/packet-landing-design-1e8003`.

- [ ] **Step 1:** Create the worktree (superpowers:using-git-worktrees): branch `feat/landing-site` from `feat/landing-opennext`.
- [ ] **Step 2:** `git checkout tannerpham/packet-landing-design-1e8003 -- docs/superpowers`, then commit `docs: add landing design and plan`.
- [ ] **Step 3:** `cd landing && npm ci && npm run build`. Expected: the build succeeds on the empty page.
- [ ] **Step 4:** Push and open a **draft** PR into `master` following the `writing-prs` skill. In the body, list the PR's blockers: D1 `database_id`, the analytics token and Tanner's review of the boundary.

### Task 1: Service area, geometry and input parsing

**Files:**
- Create: `src/config/service-area.ts`, `src/lib/geo.ts`, `src/lib/signup-input.ts`, `test/geo.test.ts`, `test/signup-input.test.ts`
- Modify: `tsconfig.json` (add `"allowImportingTsExtensions": true`), `package.json` (script `"test": "node --test test/*.test.ts"`)

**Interfaces:**
- Produces:
  - `type LatLng = readonly [lat: number, lng: number]`
  - `SERVICE_AREA: readonly LatLng[]`
  - `U_VILLAGE: LatLng = [47.6632, -122.2990]`
  - `SEATTLE_BOX = { west: -122.44, south: 47.49, east: -122.23, north: 47.74 }`
  - `pointInPolygon(p: LatLng, poly: readonly LatLng[]): boolean`
  - `round(n: number, decimals: number): number`
  - `parseQuery(body: unknown): { ok: true; q: string } | { ok: false; error: "invalid_query" }`
  - `parseSignup(body: unknown): { ok: true; value: SignupInput } | { ok: false; error: "invalid_email" }`
  - `interface SignupInput { email: string; q: string | null; utmSource: string | null; utmMedium: string | null; utmCampaign: string | null; referrer: string | null }`
- Server modules import each other with explicit `.ts` extensions, so `node --test` can load them.

`SERVICE_AREA`, first draft (clockwise). It traces the simulator drop-offs (Ave housing, Mercer Court, north campus dorms, Bryant homes, U Village hub) with a margin of about 250 m. Add a comment that Tanner reviews it before launch:
```ts
[[47.6700,-122.3175],[47.6725,-122.2990],[47.6700,-122.2920],[47.6620,-122.2930],
 [47.6580,-122.3000],[47.6540,-122.3080],[47.6540,-122.3175]]
```

- [ ] **Step 1: Write failing tests**

```ts
// test/geo.test.ts
test("U Village is inside", () => assert.equal(pointInPolygon([47.6632, -122.2990], SERVICE_AREA), true));
test("NE 45th St and Brooklyn Ave NE is inside", () => assert.equal(pointInPolygon([47.6614, -122.3140], SERVICE_AREA), true));
test("Green Lake is outside", () => assert.equal(pointInPolygon([47.6800, -122.3270], SERVICE_AREA), false));
test("Laurelhurst is outside", () => assert.equal(pointInPolygon([47.6625, -122.2780], SERVICE_AREA), false));
test("round", () => { assert.equal(round(47.66391, 2), 47.66); assert.equal(round(-122.29971, 3), -122.3); });

// test/signup-input.test.ts
test("email is trimmed and lowercased", () =>
  assert.deepEqual(parseSignup({ email: "  Ana@Example.com " }), { ok: true, value: { email: "ana@example.com", q: null, utmSource: null, utmMedium: null, utmCampaign: null, referrer: null } }));
test("bad emails are rejected", () => { for (const e of ["", "ana", "a@b", "a".repeat(250) + "@x.co", 42, null]) assert.deepEqual(parseSignup({ email: e }), { ok: false, error: "invalid_email" }); });
test("strings are capped at 200 and unknown fields ignored", () => {
  const r = parseSignup({ email: "a@b.co", utm_source: "x".repeat(500), inArea: true });
  assert.ok(r.ok && r.value.utmSource?.length === 200 && !("inArea" in r.value));
});
test("blank optional strings become null", () => { const r = parseSignup({ email: "a@b.co", q: "   " }); assert.ok(r.ok && r.value.q === null); });
test("query must be 1 to 200 characters", () => {
  assert.deepEqual(parseQuery({ q: "  " }), { ok: false, error: "invalid_query" });
  assert.deepEqual(parseQuery({ q: "x".repeat(201) }), { ok: false, error: "invalid_query" });
  assert.deepEqual(parseQuery({ q: " NE 45th St " }), { ok: true, q: "NE 45th St" });
});
```

- [ ] **Step 2:** `npm test`. Expected: FAIL (the modules are missing).
- [ ] **Step 3:** Implement the three modules.
  - `pointInPolygon` is ray casting.
  - Email rule: at most 254 characters and `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`.
  - Narrow `unknown` with `typeof` checks, not casts.
- [ ] **Step 4:** `npm test`. Expected: all pass.
- [ ] **Step 5:** `npx tsc --noEmit`. Expected: no errors.
- [ ] **Step 6:** Commit `feat(landing): service area and sign-up input parsing`.

### Task 2: Geocoder and `checkAddress`

**Files:**
- Create: `src/server/geocode.ts`, `src/server/check-address.ts`, `test/check-address.test.ts`

**Interfaces:**
- Consumes (Task 1): `SERVICE_AREA`, `SEATTLE_BOX`, `pointInPolygon`, `round`.
- Produces:
  - `type FetchFn = (input: string, init?: RequestInit) => Promise<Response>`
  - `class GeocoderError extends Error {}`
  - `geocode(q: string, fetchFn: FetchFn): Promise<LatLng | null>`, which throws `GeocoderError` on timeout, non-2xx or malformed JSON.
  - `type CheckResult = { found: false } | { found: true; inArea: boolean; lat: number; lng: number }` (lat and lng are unrounded here).
  - `checkAddress(q: string, fetchFn: FetchFn): Promise<CheckResult>`

The Nominatim request:
- URL `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=us&bounded=1&viewbox=-122.44,47.74,-122.23,47.49&q=<encoded>`;
- header `User-Agent: PacketLanding/1.0 (+[CONTACT EMAIL])`;
- a 4000 ms timeout through `AbortSignal.timeout(4000)`.

- [ ] **Step 1: Write failing tests** with a fake `fetchFn`:

```ts
test("inside point", async () => assert.deepEqual(await checkAddress("University Village", fakeJson([{ lat: "47.6632", lon: "-122.2990" }])), { found: true, inArea: true, lat: 47.6632, lng: -122.299 }));
test("outside point", async () => { const r = await checkAddress("Green Lake", fakeJson([{ lat: "47.68", lon: "-122.327" }])); assert.ok(r.found && !r.inArea); });
test("no result is not found", async () => assert.deepEqual(await checkAddress("asdfgh", fakeJson([])), { found: false }));
test("request is bounded to Seattle", async () => { let url = ""; await checkAddress("Main St", (u) => { url = u; return Promise.resolve(Response.json([])); }); assert.match(url, /bounded=1/); assert.match(url, /viewbox=-122\.44,47\.74,-122\.23,47\.49/); assert.match(url, /q=Main%20St/); });
test("5xx throws GeocoderError", async () => assert.rejects(checkAddress("x", () => Promise.resolve(new Response("", { status: 503 }))), GeocoderError));
test("429 throws GeocoderError", async () => assert.rejects(checkAddress("x", () => Promise.resolve(new Response("", { status: 429 }))), GeocoderError));
test("network failure throws GeocoderError", async () => assert.rejects(checkAddress("x", () => Promise.reject(new DOMException("timeout", "TimeoutError"))), GeocoderError));
test("malformed body throws GeocoderError", async () => assert.rejects(checkAddress("x", fakeJson({ nope: 1 })), GeocoderError));
```

- [ ] **Step 2:** `npm test`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement. Validate the response shape with type guards: an array of `{ lat: string; lon: string }` with finite numbers.
- [ ] **Step 4:** `npm test`. Expected: all pass.
- [ ] **Step 5:** Commit `feat(landing): geocode addresses and test the service area`.

### Task 3: D1 table, handlers and API routes

**Files:**
- Create: `migrations/0001_signups.sql` (exactly the spec's §10.1 SQL), `src/server/signups.ts`, `src/server/handlers.ts`, `src/app/api/check/route.ts`, `src/app/api/signup/route.ts`, `test/handlers.test.ts`
- Modify: `wrangler.jsonc` (add `d1_databases` per spec §10.3, with `database_id` set to `"local-only-replace-before-merge"` and a comment saying so), `cloudflare-env.d.ts` (regenerate with `npm run cf-typegen`)

**Interfaces:**
- Consumes: `parseQuery`, `parseSignup` (Task 1); `checkAddress`, `GeocoderError`, `FetchFn` (Task 2).
- Produces:
  - `interface SignupRow { email: string; inArea: boolean | null; lat: number | null; lng: number | null; utmSource: string | null; utmMedium: string | null; utmCampaign: string | null; referrer: string | null }`
  - `upsertSignup(db: D1Database, row: SignupRow): Promise<void>`
  - `interface Deps { db: D1Database | undefined; fetchFn: FetchFn; log: (msg: string) => void }`
  - `handleCheck(body: unknown, deps: Deps): Promise<{ status: number; body: object }>`
  - `handleSignup(body: unknown, deps: Deps): Promise<{ status: number; body: object }>`
  - The routes call these with `getCloudflareContext().env.DB`, the global `fetch` and `console.error`, and return `Response.json(body, { status })`.

Upsert SQL, which keeps `created_at` and leaves existing values alone when the new one is null:
```sql
INSERT INTO signups (email,in_area,lat,lng,utm_source,utm_medium,utm_campaign,referrer)
VALUES (?1,?2,?3,?4,?5,?6,?7,?8)
ON CONFLICT(email) DO UPDATE SET
  in_area=COALESCE(excluded.in_area,in_area), lat=COALESCE(excluded.lat,lat), lng=COALESCE(excluded.lng,lng),
  utm_source=COALESCE(excluded.utm_source,utm_source), utm_medium=COALESCE(excluded.utm_medium,utm_medium),
  utm_campaign=COALESCE(excluded.utm_campaign,utm_campaign), referrer=COALESCE(excluded.referrer,referrer),
  updated_at=datetime('now');
```

- [ ] **Step 1: Write failing tests** for the handlers, using a fake `db` that records `prepare(sql).bind(...args).run()` calls:

```ts
test("check: bad query gives 400", async () => assert.deepEqual(await handleCheck({ q: "" }, deps()), { status: 400, body: { error: "invalid_query" } }));
test("check: found rounds to 3 decimals", async () => assert.deepEqual(await handleCheck({ q: "U Village" }, deps({ geo: [47.66391, -122.29971] })), { status: 200, body: { found: true, inArea: true, lat: 47.664, lng: -122.3 } }));
test("check: geocoder failure gives 502", async () => assert.equal((await handleCheck({ q: "x" }, deps({ geoFails: true }))).status, 502));
test("signup: bad email gives 400", async () => assert.deepEqual(await handleSignup({ email: "no" }, deps()), { status: 400, body: { error: "invalid_email" } }));
test("signup: missing DB gives 503 and logs", async () => { const d = deps({ db: undefined }); assert.equal((await handleSignup({ email: "a@b.co" }, d)).status, 503); assert.match(d.logged[0], /^\[Signup:POST\] DB binding missing/); });
test("signup: stores in_area and 2-decimal location, never the address", async () => {
  const d = deps({ geo: [47.66391, -122.29971] });
  assert.deepEqual(await handleSignup({ email: "A@b.co", q: "4500 25th Ave NE", utm_source: "flyer" }, d), { status: 200, body: { ok: true } });
  assert.deepEqual(d.bound[0], ["a@b.co", 1, 47.66, -122.3, "flyer", null, null, null]);
  assert.ok(!JSON.stringify(d.bound).includes("25th"));
});
test("signup: no q stores null in_area", async () => { const d = deps(); await handleSignup({ email: "a@b.co" }, d); assert.equal(d.bound[0][1], null); });
test("signup: geocoder down still saves the email with null in_area", async () => { const d = deps({ geoFails: true }); assert.equal((await handleSignup({ email: "a@b.co", q: "x" }, d)).status, 200); assert.equal(d.bound[0][1], null); });
test("signup: insert failure gives 500 without the email in the log", async () => { const d = deps({ dbFails: true }); assert.equal((await handleSignup({ email: "a@b.co" }, d)).status, 500); assert.ok(!d.logged[0].includes("a@b.co")); assert.match(d.logged[0], /^\[Signup:POST\] Insert failed — /); });
```

- Plan decision (the spec is silent here): when the geocoder fails during sign-up, the email is still saved with null `in_area` and location, so the sign-up is never lost.

- [ ] **Step 2:** `npm test`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement `signups.ts`, `handlers.ts` and both routes. Malformed JSON bodies are treated as `{}`, giving 400.
- [ ] **Step 4:** `npm test`. Expected: all pass.
- [ ] **Step 5:** Apply the migration locally: `npx wrangler d1 migrations apply packet-landing --local`. Expected: `0001_signups.sql` applied.
- [ ] **Step 6:** `npm run preview` on port 8788. Then:
  - `curl -s -XPOST localhost:8788/api/check -d '{"q":"University Village, Seattle"}'` returns `"found":true,"inArea":true`;
  - `curl -s -XPOST localhost:8788/api/signup -d '{"email":"Test@Example.com","q":"University Village, Seattle","utm_source":"flyer"}'` returns `{"ok":true}`;
  - `npx wrangler d1 execute packet-landing --local --command "select * from signups"` shows one lowercased row with `in_area` 1 and `lat` 47.66.
- [ ] **Step 7:** Commit `feat(landing): D1 sign-ups and check/signup API`.

### Task 4: Site shell and design tokens

**Files:**
- Modify: `src/app/layout.tsx`, `src/app/globals.css`, `src/app/page.tsx`
- Create: `src/components/site/Nav.tsx`, `Footer.tsx`, `Emblem.tsx`, `SignButton.tsx`, `LeadingLines.tsx`, `SketchFilters.tsx`

**Interfaces:**
- Produces:
  - `<SignButton label: string; type?: "submit" | "button"; isBusy?: boolean; busyLabel?: string; onClick?: () => void />`: the station-sign button, mockup `.sign`.
  - `<Emblem size: number />`: geometry from §4, crop-mark offsets as in the mockup's `.emblem i`.
  - `<LeadingLines />`
  - `<SketchFilters />`: one hidden SVG with filters `pen1`, `pen2` and `pen3`, all values copied from the mockup and all `filterUnits="userSpaceOnUse"`. Rendered once in the layout.
  - `<Nav />`: Products, Press and "Get updates" (`/#updates`). The "Packet" home link shows when the path isn't `/`, and `aria-current="page"` marks the active link.
  - `<Footer />`: the emblem, "© {year} Packet. Seattle, Washington.", and links to Products, Press and Privacy. The year is computed at build time.
  - Tailwind `@theme` tokens: `--color-red`, `--color-ink`, `--color-mustard`, `--font-display`, `--font-body`, `--font-label`, and `--spacing-margin` for the side margin.

- [ ] **Step 1:** Set up the fonts with `next/font/google` (`Libre_Franklin` 400/600, `Atkinson_Hyperlegible_Next` 400/700, `Barlow_Condensed` 600) as CSS variables. Set metadata to title "Packet", description "Delivery from U Village shops to homes nearby, by autonomous aircraft." Remove the starter's dark-mode block.
- [ ] **Step 2:** Add the analytics beacon in the layout: render `<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon={JSON.stringify({ token })} />` only when `process.env.NEXT_PUBLIC_CF_BEACON_TOKEN` is set. No SRI hash: Cloudflare serves this beacon from a moving URL and does not publish one.
- [ ] **Step 3:** Port the shell CSS from the mockup into `globals.css`: the 8px band, the `[hidden]` rule, focus outlines, the sketch-filter selectors, the reduced-motion block. Build the components.
- [ ] **Step 4:** `npm run build && npm run lint`. Expected: both pass.
- [ ] **Step 5:** Run `npm run preview` and screenshot `/` at 375 and 1440. Expected: the band, the nav in Libre Franklin and the footer emblem match `home-1440.png` (top and bottom).
- [ ] **Step 6:** Commit `feat(landing): site shell, tokens and shared marks`.

### Task 5: Canvas toolkit and hero globe

**Files:**
- Create: `scripts/fetch-streets.mjs`, `src/data/streets.json`, `src/lib/canvas/loop.ts`, `src/lib/canvas/sphere.ts`, `src/lib/canvas/marks.ts`, `src/components/home/HeroGlobe.tsx`, `src/components/home/useGlobeAim.ts`

**Interfaces:**
- Consumes: `SERVICE_AREA`, `U_VILLAGE`, `LatLng` (Task 1).
- Produces:
  - `mountCanvas(canvas: HTMLCanvasElement, draw: (ctx: CanvasRenderingContext2D, w: number, h: number, t: number) => void, opts: { isAnimated: boolean }): { paint: () => void; destroy: () => void }`. It handles DPR, resize, pause when off screen or `document.hidden` (IntersectionObserver plus `visibilitychange`), and draws a single frame under reduced motion.
  - `project(o: SphereView, lon: number, lat: number): [x: number, y: number, z: number]`
  - `drawSphere(ctx, w, h, o: SphereView, streets: Streets, outline: readonly LatLng[]): void`
  - `drawMarks(ctx, x, y, s, k, lw, hasBlock): void` (the mockup's `marks`)
  - `<HeroGlobe target: LatLng | null />`: turns to `target` and closes the corner marks on it. `null` means drift.
- `streets.json` shape: `{ main: LatLng[][]; minor: LatLng[][] }`.

- [ ] **Step 1:** Write `fetch-streets.mjs`.
  - Query Overpass for `highway` in (primary, secondary, tertiary) as main and (residential, unclassified) as minor, within 2.5 km of `U_VILLAGE`.
  - Simplify with Douglas–Peucker at about 8 m and round coordinates to 5 decimals.
  - Write `src/data/streets.json`. Add `// Data © OpenStreetMap contributors, ODbL` to the script header.
- [ ] **Step 2:** Run `node scripts/fetch-streets.mjs`. Expected: the JSON is under 250 KB and has at least 20 main and 100 minor lines.
- [ ] **Step 3:** Port the mockup's `sphere`, `project`, `marks` and `aim` into the modules above.
  - Map lat/lng to sphere lon/lat around `U_VILLAGE`.
  - Draw the service outline as a dotted line in black at 60% opacity.
  - Keep the globe parameters from the mockup: `cx: narrow ? w*0.78 : w*0.88`, `cy: narrow ? h*0.95 : h*0.86`, `R: narrow ? w*0.95 : max(w,h)*0.6`, `roll: -0.5`, drift `[t*0.03, 0.42]`.
  - Main streets are darker than minor ones.
- [ ] **Step 4:** Mount `<HeroGlobe target={null} />` in the hero area. Build, preview and screenshot at 390 and 1440. Expected:
  - the globe sits low and right like `home-1440.png`;
  - the streets are recognizably U Village (25th Ave NE, NE 45th St and Montlake curve visible);
  - the outline is visible;
  - nothing runs under the copy.
- [ ] **Step 5:** Commit `feat(landing): halftone globe with U Village streets`.

### Task 6: Hero sign-up flow and attribution

**Files:**
- Create: `src/lib/attribution.ts`, `src/components/home/Hero.tsx`, `src/components/home/AddressForm.tsx`, `src/components/home/useSignupFlow.ts`

**Interfaces:**
- Consumes: `<HeroGlobe>` (Task 5); `<SignButton>` (Task 4); the `/api/check` and `/api/signup` contracts (Task 3).
- Produces:
  - `captureAttribution(): void`: on first load, stores `utm_source`, `utm_medium`, `utm_campaign` from `location.search` and `document.referrer` in `sessionStorage` key `packet:attr`. It never overwrites an existing value, and wraps storage access in try/catch.
  - `readAttribution(): { utm_source?: string; utm_medium?: string; utm_campaign?: string; referrer?: string }`
  - `submitSignup(email: string, q: string | null): Promise<"ok" | "invalid_email" | "error">`: shared with Task 7.
  - `useSignupFlow()`: returns `{ step: "address" | "email" | "done"; status: "idle" | "checking" | "sending"; heading: string; hint: string; error: string; target: LatLng | null; onCheck(q: string): void; onSubmit(email: string): void; onRestart(): void }`.

- [ ] **Step 1:** Build the hero from §6.1:
  - h1 "Packet";
  - the address field (label "Street address or cross streets", placeholder "NE 45th St and 25th Ave NE");
  - "Check", then the email step and "Check another address";
  - every message string exactly as in §6.1;
  - `role="status" aria-live="polite"` on the message line;
  - the App Store line.
- [ ] **Step 2:** Guard in-flight requests. While `status !== "idle"`, `onCheck` and `onSubmit` return early, and the button shows "Checking…" or "Sending…" and is disabled. On any error, the field values stay and the status returns to `idle`.
- [ ] **Step 3:** Handle `#updates`. On load and on `hashchange`, scroll to the hero and focus the address field (§16).
- [ ] **Step 4:** Build, then preview with local D1. Open `/?utm_source=flyer&utm_medium=qr&utm_campaign=uvillage-1` in a real browser and check:
  - "University Village, Seattle": inside message, globe turns.
  - "Green Lake, Seattle": outside message.
  - "asdfgh": not-found message.
  - Empty field: "Enter a street address or cross streets."
  - Double-click "Check": only one `/api/check` request in the network panel.
  - With the network offline: "Something went wrong. Try again in a moment.", the input kept, the button re-enabled.
  - Submit an email: "You're on the list." The D1 row has `in_area` 1, `utm_source` flyer, `utm_medium` qr, `utm_campaign` uvillage-1.
- [ ] **Step 5:** Commit `feat(landing): address check and sign-up in the hero`.

### Task 7: Closing call to action and tunnel

**Files:**
- Create: `src/components/home/ClosingCta.tsx`, `src/components/home/TunnelCanvas.tsx`, `src/components/home/EmailForm.tsx`

**Interfaces:**
- Consumes: `submitSignup` (Task 6), `mountCanvas` (Task 5), `<SignButton>` (Task 4).
- Produces: `<ClosingCta />`.

- [ ] **Step 1:** Build it per §6.6: the h2, the email field, "Get updates" (the screen's one station-sign button), the status line and the App Store line. It calls `submitSignup(email, null)`.
- [ ] **Step 2:** Port the mockup's tunnel draw: `D0 = tile*0.75`, `q = 1.42`, `f = (t*0.2)%1`, rotation `0.025*(i+f)`, a fade near the center. **No center square.**
- [ ] **Step 3:** Preview check:
  - submitting stores a row with null `in_area`;
  - the tunnel animates;
  - it freezes under reduced motion (DevTools rendering emulation).
- [ ] **Step 4:** Commit `feat(landing): closing sign-up with crop-mark tunnel`.

### Task 8: What, How it works, Mission

**Files:**
- Create: `src/components/home/WhatSection.tsx`, `src/components/home/HowItWorks.tsx`, `src/components/home/TripCanvas.tsx`, `src/components/home/useScrollProgress.ts`, `src/components/home/Mission.tsx`, `src/components/drawings/VehiclePlanSide.tsx`, `src/components/home/useDrawIn.ts`

**Interfaces:**
- Consumes: `drawMarks`, `mountCanvas` (Task 5); `<LeadingLines>` (Task 4).
- Produces:
  - `useScrollProgress(ref, start = 0.85, span = 0.6): number`: 0 to 1, as in the mockup's `onScroll`.
  - `useDrawIn(ref): boolean`: true once the element's top passes 75% of the viewport height, then stays true.
  - `<VehiclePlanSide />`: the mockup's mission SVG (callouts at their final positions, filter applied to shapes only), plus the legend and the caption.

- [ ] **Step 1:** WhatSection, with copy from §6.2 including "Packet starts in University Village and the streets around it, including the U District, Bryant and the UW campus."
- [ ] **Step 2:** HowItWorks. The trip canvas follows scroll progress, and the bullets fill at 0, 0.5 and 0.999. The three step texts come from §6.3.
- [ ] **Step 3:** Mission, with copy from §6.4. The drawing draws in with `pathLength="1"` and a stroke-dashoffset transition. The second pen pass is rendered in JSX: a fainter copy of each line element with filter `pen2`, offset `translate(.8px,.6px)` at 45% opacity. Nothing is cloned in the DOM.
- [ ] **Step 4:** Preview at 390 and 1440, scrolled through. Expected:
  - the trip moves with scroll;
  - the drawing draws in once;
  - callouts don't overlap the drawing lines;
  - it matches `home-1440.png`.
- [ ] **Step 5:** Commit `feat(landing): what, how it works and mission sections`.

### Task 9: Sketched drawings and product data

**Files:**
- Create: `src/components/drawings/VehicleSide.tsx`, `AppPhone.tsx`, `DispatchMap.tsx`, `ItemBowl.tsx`, `ItemWrap.tsx`, `ItemCup.tsx`, `ItemBox.tsx`, `src/data/products.ts`, `src/data/store-items.ts`, `src/data/news.ts`

**Interfaces:**
- Produces:
  - `interface Product { id: "vehicle-01" | "app" | "dispatch"; no: string; name: string; line: string; linkLabel: string; description: string; specs: readonly { key: string; value: string }[]; Drawing: () => React.JSX.Element }`
  - `PRODUCTS: readonly Product[]`, in order vehicle-01, app, dispatch, with every string copied from spec §6.5 and §7.
  - `STORE_ITEMS: readonly { name: string; shop: string; price: string; Drawing: () => React.JSX.Element }[]`
  - `NEWS: readonly { date: string; headline: string; summary: string }[]` (from §8).
- Drawing paths are copied from the mockup's plate and item SVGs. Each drawing component sets its own `viewBox` and applies filter `pen3` to shapes.

- [ ] **Step 1:** Create the drawings and the three data files.
- [ ] **Step 2:** `npx tsc --noEmit && npm run lint`. Expected: both pass.
- [ ] **Step 3:** Commit `feat(landing): product drawings and content data`.

### Task 10: Product showcase

**Files:**
- Create: `src/components/home/Showcase.tsx`, `src/components/home/useShowcase.ts`

**Interfaces:**
- Consumes: `PRODUCTS` (Task 9).
- Produces:
  - `useShowcase(count: number, durationMs = 7000)`: returns `{ index: number; isPlaying: boolean; go(i: number): void; next(): void; togglePlay(): void; restartWait(): void }`.
  - Auto-advance only runs when `isPlaying`, reduced motion is off and `document.visibilityState === "visible"`. Returning to the tab restarts a full wait.

- [ ] **Step 1:** Build it per §6.5, porting the mockup's `.stage`, `.slide`, `.peek`, `.next` and tab CSS:
  - inactive slides are `inert`;
  - the peek shows the next product's `Drawing` at 50% opacity, translated 45% off the edge;
  - the "Next" label shows the next product's name, and is hidden under 760px;
  - a swipe of more than 48px changes the product;
  - pointer-down, key presses and focus inside the section call `restartWait`;
  - each "About …" link goes to `/products#{id}`.
- [ ] **Step 2:** Preview checks:
  - it advances after 7s and wraps from 03 back to 01;
  - the arrow, the tabs and swiping each work;
  - after pause, nothing advances for 20s;
  - with the tab hidden for 10s, it hasn't moved on return;
  - under reduced motion, nothing advances and nothing transitions;
  - Tab moves through the arrow, the tabs and pause, with visible focus and accessible labels.
- [ ] **Step 3:** Commit `feat(landing): one-at-a-time product showcase`.

### Task 11: Products page

**Files:**
- Create: `src/app/products/page.tsx`, `src/components/products/ProductSection.tsx`, `src/components/products/StorePreview.tsx`

**Interfaces:**
- Consumes: `PRODUCTS`, `STORE_ITEMS` (Task 9).

- [ ] **Step 1:** Build it per §7:
  - the intro;
  - a `ProductSection` per product with `id={product.id}`, alternating sides (`flip` on odd indexes) and a spec `<dl>`;
  - the store preview with the mustard "Preview" tag, the copy and four cards (two columns under 760px), ending with the "Get updates when ordering opens" link to `/#updates`.
- [ ] **Step 2:** Preview. `/products#dispatch` lands on Dispatch, and screenshots at 390 and 1440 match `products-1440.png`.
- [ ] **Step 3:** Commit `feat(landing): products page with U Village preview`.

### Task 12: Press and Privacy pages

**Files:**
- Create: `src/app/press/page.tsx`, `src/components/press/ManualSection.tsx`, `src/app/privacy/page.tsx`

**Interfaces:**
- Consumes: `NEWS` (Task 9), `<Emblem>` (Task 4).
- Produces: `<ManualSection no: string; title: string; children />`: the numbered manual row.

- [ ] **Step 1:** Build Press per §8: 1.0 Fact sheet (the rows exactly as in the spec), 2.0 News from `NEWS`, 3.0 Brand plates and ink swatches, 4.0 Contact.
- [ ] **Step 2:** Draft Privacy per §13 in plain sentences. Include:
  - what's collected;
  - that the address is sent to Nominatim and never stored;
  - visits counted without cookies;
  - no data sold;
  - removal by emailing [CONTACT EMAIL];
  - "Map data © OpenStreetMap contributors" and Nominatim attribution.
  - Mark the page **draft for Tanner's approval** in the PR body, not on the page.
- [ ] **Step 3:** Preview and screenshot at 390 and 1440. Expected: matches `press-1440.png`.
- [ ] **Step 4:** Commit `feat(landing): press kit and privacy notice`.

### Task 13: Placeholder report and full verification

**Files:**
- Create: `scripts/check-placeholders.mjs`
- Modify: `package.json` (`"check:placeholders": "node scripts/check-placeholders.mjs"`)

- [ ] **Step 1:** Write the script. It greps `src/` for `\[[A-Z][A-Z ]+\]`, prints `file:line  [TOKEN]` for each hit, exits 0 and is not wired into the build.
- [ ] **Step 2:** `npm run check:placeholders`. Expected: it lists the spec §14 placeholders and nothing unexpected.
- [ ] **Step 3:** Run `npm test && npm run lint && npm run build`. Expected: all pass.
- [ ] **Step 4:** Run `npm run preview` and screenshot `/`, `/products` and `/press` at 375, 430, 768, 1280, 1440 and 1920. Expected: no horizontal scroll and no clipped text. Attach the screenshots to the PR.
- [ ] **Step 5:** Re-run the full §15 checklist in one pass and record the results in the PR body, in Verified / Not verified / For Tanner form.
- [ ] **Step 6:** Commit, push, and **leave the PR in draft**. Also list the Figma write-back (spec §9) as a follow-up for Tanner. Report the blockers for Tanner: `database_id` and the remote migration, the analytics token, review of the boundary outline, approval of the privacy text, and the placeholder list.
