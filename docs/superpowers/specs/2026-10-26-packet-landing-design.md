# Packet landing site design

Date: 2026-10-26
Status: draft, awaiting approval
Mockup: `2026-10-26-packet-landing/mockup.html` (also published as the "Packet Hero Studies" artifact, version 19)
Reference images: `2026-10-26-packet-landing/*.png`
Design rules: Figma "Packet Design Rules", file `4BYLJVuIxmKgKuFcOJZOg1`

## 1. Intent

Packet is a logistics and autonomous delivery company. It starts with orders from University Village (U Village) shops in Seattle, flown to homes nearby. Packet is not a drone company: the aircraft is the first product of a delivery system.

Nothing has launched. The site's job is to **advertise and capture interest**:

- explain what Packet is and how it works, so a visitor understands it in one screen;
- let people check whether Packet will reach them and leave an email for updates;
- record where each visitor came from (flyer QR code, social ad, word of mouth) so the team knows which channel works.

Visitors arrive from printed flyers, social ads and friends. They are UW students and anyone else living near U Village. Most land on a phone.

## 2. Goals, non-goals, anti-goals

Goals
- A visitor can check whether their street is in the service area, by street address or cross streets, and sign up for updates from the first screen, on phone and desktop.
- Every sign-up is stored with whether it is in the service area, a coarse location (about 1 km), the campaign tags from the link (`utm_source`, `utm_medium`, `utm_campaign`) and the referrer. The address itself is never stored.
- Visits are counted (page views, sources) without cookies.
- Products and Press pages that read as a real company's pages, not placeholders.

Non-goals (this build)
- Ordering or payment on the web. Orders happen in the iOS app, which is not yet on the App Store.
- An admin screen for sign-ups. The team reads them with `wrangler d1 execute`.
- Confirmation emails, unsubscribe flows, newsletters, spam protection. Add Cloudflare Turnstile only if spam appears.
- Dark mode. The site is a single light look on purpose (design rule 0.6, white pages).
- A real store. The "From U Village shops" section is a static preview.

Anti-goals (would make the build a failure even if it works)
- Anything that reads as a class project. No "CSE 589", university name, team name or "student project" anywhere public. Packet is presented as a company.
- Startup marketing voice: no "seamless", "revolutionary", "magic", no em dashes in copy, no claims the product can't back up (for example "speed of light", invented specs).
- A drone company look. The aircraft only ever appears as a technical drawing (rule 0.2, scoped; see §9).
- A heavy backend. One table, two small endpoints, one external geocoder.
- Ad-platform trackers (Meta, Google) or a consent banner.

## 3. Constraints

- Code lives in `landing/` on branch `feat/landing-opennext`, merge target `master`. Package manager **npm**.
- Stack already set up: Next 16.4, React 19, Tailwind 4, `@opennextjs/cloudflare`, Wrangler 4. The site runs as one Cloudflare Worker named `landing`.
- **Merging to `master` deploys production** through Cloudflare Workers Builds (see `landing/README.md`). Merge only with Tanner's go-ahead.
- Strict TypeScript: no `any`, no `as` casts. One component per file, `PascalCase.tsx`, a named `Props` interface above each component.
- Errors are logged as `[Module:Function] Description — {context}` with no email addresses in logs.
- Verify against the built site (`npm run build`, then `npm run preview` on the Cloudflare runtime), not `next dev`.
- Creating the D1 database on the Cloudflare account and applying the migration remotely wait for Tanner. Local D1 (`wrangler d1 migrations apply --local`) is fine.

## 4. Visual system

All from the Figma rules sheet. The mockup is the reference for every value below.

Inks (exactly four, as CSS tokens): Packet Red `#B4432F`, Black `#111111`, Mustard `#D3A13F`, White `#FFFFFF`. One extra neutral, `#d9d9d9`, is used only for the showcase progress track.

Type
- Libre Franklin 600: wordmark, headings, nav links, footer links.
- Atkinson Hyperlegible Next 400/700: body text, buttons, form inputs.
- Barlow Condensed 600, uppercase, tracked: short labels only (field labels, spec table keys, section numbers, "Next").
- IBM Plex Mono is never used on the site.
- Load all three with `next/font/google`.

Layout
- Side margin `clamp(20px, 6.5vw, 96px)`, respecting safe-area insets. One left edge for all content.
- Controls are 44px tall with 16px text (`--control-h`, `--control-font`). Field labels 12px.
- An 8px black band runs across the top of every page.

Signature elements
- **Emblem**: the wordmark inside four crop marks. With x = cap height: trim x/2, marks 0.4x long, offset 0.15x from the corner, stroke x/16. Used in the footer and on the Press page. It is the only ornament.
- **Station-sign button**: black, 4px radius, a thin white band across the top, the arrow module first, the label flush left. **One per screen.**
- **Leading lines**: red, mustard and black bars (8px, 4px gap) running from the margin off the right edge. Used once, in the "what" section. Never as a divider or progress bar.
- **Mustard tag**: at most one per screen ("Preview" on Products).
- **Red block**: the package or delivery icon. Appears in the "How it works" route icon and inside drawings as the payload.
- **Sketched drawings**: technical line drawings with a hand-drawn wobble. Built as inline SVG with two `feTurbulence` + `feDisplacementMap` filters: a main pen pass and a second fainter, offset pass. Use `filterUnits="userSpaceOnUse"` so straight lines don't vanish. Text inside drawings is not filtered.

Motion
- Every animation has a `prefers-reduced-motion` path: motion stops and every element shows in its final state.
- Canvas animations pause when off screen.

## 5. Site map

| Route | Purpose |
|---|---|
| `/` | Landing page |
| `/products` | Products, with anchors `#vehicle-01`, `#app`, `#dispatch`, and the U Village preview |
| `/press` | Press kit |
| `/privacy` | Privacy notice (drafted by the builder, approved by Tanner before launch) |
| `POST /api/signup` | Stores a sign-up |

The mockup fakes the subpages as hash views. The build uses real routes. The nav shows Products, Press and Get updates; on subpages a "Packet" home link appears at the left. Get updates links to `/#updates` and focuses the address field.

## 6. Landing page, top to bottom

See `home-1440.png` and `home-390-sheet.png`.

### 6.1 Hero: sign-up over a turning globe
- Left: h1 "Packet" (Libre Franklin 600, `clamp(64px, 9vw, 136px)`). Under it, the sign-up form in two steps that share one slot:
  1. "Is Packet coming to your street?" One field, labeled "Street address or cross streets", with placeholder "NE 45th St and 25th Ave NE", and a station-sign button, "Check".
  2. After the check, the result line plus an email field and "Get updates". A "Check another address" text button returns to step 1.
- The mockup still shows a ZIP field. The field changes as described here; the layout and button do not.
- Result copy. The question line is replaced by the result, and a hint line sits under the form:
  - Inside: "That's inside the first area around U Village." Hint: "Get an email when Packet launches."
  - Outside: "That's outside the first area, for now." Hint: "Get an email when Packet reaches your street."
  - Not found: "We couldn't find that address. Try cross streets, like NE 45th St and 25th Ave NE."
  - Empty field: "Enter a street address or cross streets."
  - Invalid email: "Enter an email address, like you@example.com."
  - Success: "You're on the list." (both forms)
  - Server or geocoder error: "Something went wrong. Try again in a moment." The entered values stay in the fields.
  - While checking or sending, the button reads "Checking…" or "Sending…" and is disabled.
- Small line under the form: "Packet for iPhone is coming to the App Store [LAUNCH DATE]."
- Right (behind the copy, bleeding off the edge): a canvas **halftone globe**. The street grid around U Village is drawn as dots on a sphere, tilted (`roll -0.5`) and sitting low and right, not centered. It drifts slowly.
  - On a check, the globe turns so the found point lands beside the copy, and four corner marks close in on it. The service-area boundary is drawn on the globe as a dotted outline, so inside and outside are visible.
  - The anchor-solving approach is in the mockup's `aim()` function.
  - Use real U Village streets (§6.9).
- On phones the globe sits above the copy, 300px tall.

### 6.2 What
- h2 "Delivery from U Village shops to homes nearby."
- The leading lines.
- Body copy: "Order in the Packet app, follow it as it comes, and find it at your front door. Packet starts in University Village and the streets around it, including the U District, Bryant and the UW campus." This replaces the mockup's "[RADIUS]".

### 6.3 How it works
- h2 "Three steps, all in the app."
- A scroll-driven canvas: the red block inside its corner marks travels a dotted route, leaving a mustard trail. The three numbered bullets fill as it passes each step.
- Steps: Order ("Pick from [VENDOR]'s menu at U Village and pay in the app."), Follow it, At your door.

### 6.4 Mission
- Left: h2 "Autonomous delivery, built around the way you live." Lead line: "From point A to point B faster than the road allows, and lighter on the streets you share." Then: "Vehicle 01 is the first: a four-rotor aircraft that flies an order from U Village to your door."
- Right: the sketched **Vehicle 01 drawing**, plan view and side view:
  - centerlines;
  - dashed rotor discs;
  - span and height dimension lines marked `[TBD]`;
  - callouts 1 to 4 (rotor, body, payload, landing legs);
  - the payload drawn as the red block.
- A legend sits under the drawing, then "Vehicle 01. Not to scale. Dimensions to follow."
- The lines draw in once (stroke-dashoffset), when the figure's top passes 75% of the viewport height.
- The drawing is generic until real specs exist. Keep it data-driven so dimensions can be filled in later.

### 6.5 Product showcase
- h2 "One system, from the shop to your door."
- One product at a time, set like a hero:
  - copy on the left: number, a large name `clamp(40px, 5vw, 72px)`, one line, an "About …" link to `/products#…`;
  - that product's sketched drawing on the right.
- Products:
  - 01 Vehicle 01: "The four-rotor aircraft that carries each order. Payload [TBD]."
  - 02 Packet for iPhone: "Order from U Village shops and follow each step to your door."
  - 03 Dispatch: "Plans each flight and follows it from pickup to drop-off."
- Bottom right: a round 56px arrow button, labeled "Next" over the next product's name (only the arrow shows on phones).
- Past it, a faded (50%), mostly off-screen slice of the next product's drawing peeks from the corner.
- Transition:
  - the current copy fades out;
  - the incoming drawing grows from the bottom-right corner (from `translate(14%,10%) scale(.7)` to rest);
  - the copy fades in after 150ms.
- Auto-advance: after 7s with no interaction, it moves to the next product and wraps from 03 back to 01.
  - A pointer-down, key press or focus inside the section restarts the 7s.
  - A horizontal swipe of more than 48px changes the product.
- Controls under the stage:
  - three 44px progress tabs that fill over 7s and jump to a product when tapped;
  - a pause/play button (required for auto-moving content).
- Reduced motion: no auto-advance, no transitions.
- Inactive products are `inert`.
- There is no marquee band and no visible carousel track. Both were tried and rejected.

### 6.6 Closing call to action
- Left: h2 "Hear when Packet reaches your street." An email field and "Get updates" (this screen's one station-sign button). The App Store line repeats.
- This form has no address step. It posts with only the email, so `in_area` is null.
- Right: the **crop-mark tunnel**, a canvas of dotted corner marks rushing toward a vanishing point:
  - rings at `D0·q^(i+f)`;
  - a slight twist per ring;
  - fading near the center.
- **No square or icon at the center.** Several were tried and rejected.

### 6.7 Footer
- The emblem, then "© [YEAR] Packet. Seattle, Washington."
- Links, right-aligned: Products, Press, Privacy.

### 6.8 Removed from the mockup for the build
- The "Working notes" disclosure.

### 6.9 Real streets in the globe
Replace the stylized grid with U Village area streets, a simplified set of main and minor streets, from OpenStreetMap data.
- Bake it into a small static JSON at build time or by a one-off script committed with its output.
- Keep ODbL attribution in the footer or on `/privacy`.
- Main streets render darker than minor ones.

## 7. Products page

See `products-1440.png`.

- Intro: h1 "Products". Lead: "Three parts that take an order from a U Village shop to your door."
- Three product sections, in showcase order, alternating copy and drawing sides. Each has the number, h2 name, two sentences and a spec table (Barlow keys, hairline rows).
  - **Vehicle 01**: Rotors 4. Payload, Range, Cruise speed, Flight altitude and Weather limits all `[TBD]`.
  - **Packet for iPhone**: Platform iPhone; Availability "App Store, [LAUNCH DATE]"; Order from U Village shops; Delivery area "University Village and the streets around it"; Payment [TBD].
  - **Dispatch**: Assigns "One aircraft per order"; Plans "Route and altitude for each flight"; Follows "Each flight from pickup to drop-off"; Hours [TBD]. **Tanner to confirm** this wording is accurate and fine to publish.
- **From U Village shops** (preview): an 8px black rule, the mustard "Preview" tag, h2, and "Some of what Packet will deliver at launch. Shops, items and prices to follow. Orders open in the app."
  - A grid of four item cards (two columns on phones). Each card has a sketched item drawing, the item name, the shop and the price.
  - Items come from the app's mock menu: U Village Bowl, Drumstick Wrap, Cold Brew, plus one [ITEM].
  - Shop names stay `[SHOP]` until each shop agrees to be listed.
  - No buttons; the section ends with the link "Get updates when ordering opens".
  - Data lives in one typed array so items can be swapped without layout changes.

## 8. Press page

See `press-1440.png`. Laid out like a corporate manual: numbered sections (1.0 to 4.0) in a narrow left column, content on the right, a 1.5px rule above each section.

- **1.0 Fact sheet**: Company Packet; Founded [YEAR]; Based in Seattle, Washington; Service area "University Village, Seattle, and the streets around it"; First product "Vehicle 01, a four-rotor delivery aircraft"; Deliveries begin [LAUNCH DATE]; Leadership "[NAME], [TITLE] · [NAME], [TITLE]".
- **2.0 News**: a dated list with headline and one-line summary. Two entries in the mockup: "Packet plans autonomous delivery for University Village" and "Packet for iPhone opens sign-ups". The data lives in one typed array.
- **3.0 Brand**: framed plates for 3.1 Emblem, with its usage rule, and 3.2 Typefaces. Below them, four ink swatches with names, hex values and where each is used, then a download line with `[DOWNLOAD LINK]`.
- **4.0 Contact**: Press [NAME], [EMAIL]; Photos and interviews [EMAIL].

## 9. Rule changes to write back into Figma

- 0.2 "Never show the drone" becomes: the aircraft appears only as a technical drawing (Products, Press and the landing page's mission section).
- Sketched-line technique for drawings (the two-pass pen filter).

## 10. Sign-ups: Worker and D1

One D1 database bound to the existing `landing` Worker as `DB`. One migration, one route handler.

### 10.1 Schema (`landing/migrations/0001_signups.sql`)

```sql
CREATE TABLE signups (
  email         TEXT PRIMARY KEY,          -- lowercased, trimmed
  in_area       INTEGER,                   -- 1, 0, or null when no address was checked
  lat           REAL,                      -- rounded to 2 decimals (about 1 km), null without a check
  lng           REAL,
  utm_source    TEXT,
  utm_medium    TEXT,
  utm_campaign  TEXT,
  referrer      TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
```

The address text is never stored or logged. A repeat sign-up with the same email upserts: it keeps `created_at`, overwrites the other fields when the new value is non-null, and bumps `updated_at`.

### 10.2 Endpoints

Both are route handlers in `landing/src/app/api/`. Both use one shared server function, `checkAddress(q)`, which:
- geocodes the query;
- tests the point against the service-area boundary (§11);
- returns `{ found, inArea, lat, lng }`.

**`POST /api/check`**: body `{ q }`.
- Returns `200 { found: false }`, or `200 { found: true, inArea, lat, lng }` with lat and lng rounded to 3 decimals for the globe aim.
- Returns `400 { error: "invalid_query" }` for an empty query or one over 200 characters.
- Returns `502 { error: "geocoder" }` when the geocoder fails.

**`POST /api/signup`**: body `{ email, q?, utm_source?, utm_medium?, utm_campaign?, referrer? }`.
- When `q` is present, the server runs `checkAddress(q)` itself. It never trusts a client-sent `inArea`.
- It stores `in_area` and the location rounded to 2 decimals.
- Validation:
  - email is at most 254 characters and has the shape `x@y.z`;
  - other strings are trimmed and capped at 200 characters;
  - unknown fields are ignored.
- Responses:
  - `200 { ok: true }`;
  - `400 { error: "invalid_email" }`;
  - `500 { error: "server" }`, logged as `[Signup:POST] Insert failed — {in_area, utm_source}`, never the email or address;
  - `503 { error: "unavailable" }` when the DB binding is missing.

The client keeps the UTM fields from the landing URL (and the referrer) in `sessionStorage`, so they survive navigation to subpages before signing up.

**Geocoder.** Nominatim (OpenStreetMap), called only from the Worker:
- query `format=jsonv2&limit=1&countrycodes=us&viewbox=<Seattle bbox>&bounded=1`;
- a descriptive `User-Agent` with a contact address;
- a 4s timeout.

This follows Nominatim's usage policy: low volume, no autocomplete, attribution on `/privacy`. If traffic outgrows it, swap the geocoder inside `checkAddress` only; nothing else changes.

### 10.3 Config and bindings
- Add to `wrangler.jsonc`: `"d1_databases": [{ "binding": "DB", "database_name": "packet-landing", "database_id": "<from wrangler d1 create>", "migrations_dir": "migrations" }]`. Then rerun `npm run cf-typegen`.
- **Tanner runs** `wrangler d1 create packet-landing` and the remote migration. The builder uses local D1 for verification.
- *Builder call (2026-10-26):* the binding goes in the branch with the real `database_id` before the PR leaves draft. Until Tanner supplies the id, the PR stays draft and is not merged, so a placeholder id never reaches a production deploy. If `env.DB` is missing at runtime, the route returns `503 { error: "unavailable" }` and logs `[Signup:POST] DB binding missing`.

## 11. Service area config

`landing/src/config/service-area.ts` is the single source of truth, used by the API, the globe outline and the copy.

- The boundary is a polygon (a list of lat/lng points) drawn tightly around U Village. At launch it covers University Village and the nearby streets the team plans to fly to: the U District, Bryant, Mercer Court and the UW campus. It excludes the rest of ZIP 98105 (Laurelhurst, Ravenna, Roosevelt, Wallingford).
- *Builder call:* the first polygon traces the drop-off points in the team's traffic simulator (`sim/*` branches, `traffic-simulator/config/waypoints.json`) with a small margin. **Tanner reviews the outline on the globe before launch.**
- The inside test is point-in-polygon (ray casting), a few lines with no dependency.
- Changing the area means editing the polygon only.

## 12. Analytics

Cloudflare Web Analytics: no cookies, no consent banner. Add the beacon script in `layout.tsx`, using the site token from the Cloudflare dashboard (**Tanner provides it**). No ad-platform pixels.

*Builder call:* the token is read from a build-time env var (`NEXT_PUBLIC_CF_BEACON_TOKEN`), and the beacon is not rendered when it is unset. No placeholder token ever ships.

## 13. Privacy page

A short, plain notice, drafted by the builder and approved by Tanner before launch:
- what is collected (email; whether the address is in the service area and a location rounded to about 1 km; campaign tags; referrer). The address typed into the check is sent to OpenStreetMap's Nominatim service to find it, and is not stored. Why it is collected (to tell people when Packet reaches them and to learn which flyers and ads work);
- that page visits are counted without cookies;
- that no data is sold;
- how to be removed: email [CONTACT EMAIL];
- the OpenStreetMap and Nominatim attribution.

## 14. Placeholders to fill before going public

The build ships with these as visible `[BRACKETS]`. All must be replaced before the site is promoted:
- launch date;
- the first vendor and shop names;
- the Vehicle 01 specs (payload, range, speed, altitude, weather, dimensions);
- payment methods;
- dispatch hours;
- founded year;
- leadership names and titles;
- press and contact emails;
- the brand download link;
- the Web Analytics token.

*Builder call:* `npm run check:placeholders` (a short script that greps `src/` for `[UPPERCASE]` brackets) lists what's left. It is run before promoting the site, and is not wired into the build, so deploys are never blocked by it.

## 15. Verification (what "done" means)

- `npm run build` and `npm run lint` pass, with no TypeScript errors.
- `npm run preview` (Cloudflare runtime) with local D1. Checked in a real browser:
  - **Address check**:
    - "University Village, Seattle" and "NE 45th St and Brooklyn Ave NE" give the inside message;
    - "Green Lake, Seattle" gives the outside message;
    - "asdfgh" gives the not-found message.
    - The globe turns to the point each time.
    - `checkAddress` and the point-in-polygon test also get a small unit check with fixed coordinates, so they can be tested without the network.
  - **Hero sign-up**: one row appears in local D1 with `in_area`, rounded `lat`/`lng` and the UTM fields from `/?utm_source=flyer&utm_medium=qr&utm_campaign=uvillage-1`. No address text is in the row or the logs.
  - **Repeat sign-up**: the same email upserts and doesn't duplicate.
  - **Closing form**: stores a row with null `in_area`.
  - **Bad input**: posting it directly to the API returns 400.
  - **Showcase**: advances after 7s; the arrow, the tabs, swiping and pause work; the About links land on the right product on `/products`.
  - **Mission drawing**: draws in on scroll.
  - **Reduced motion**: nothing moves on its own.
- Screenshots at 375, 430, 768, 1280, 1440 and 1920 for `/`, `/products` and `/press`:
  - no horizontal scroll, nothing clipped;
  - compared against the reference images in this folder.
- Keyboard: every control is reachable with visible focus, and the showcase controls have labels.

## 16. Left to the builder

- Component breakdown and file layout under `landing/src`, within the house rules.
- How the canvas pieces (globe, trip, tunnel) share the halftone and corner-mark helpers.
- The exact OSM extraction and simplification approach for streets.
  - *Builder call:* a one-off script in `landing/scripts/` queries Overpass (network allowed) for roughly 2.5 km around U Village, enough to show the boundary with streets beyond it. It simplifies the result, commits it as `src/data/streets.json`, and the script is committed alongside it.
- Cross-route "Get updates" focus. *Builder call:* on `/` the page reads `#updates` on load and on `hashchange`, scrolls to the hero and focuses the address field.
- The Figma file needs authorization in build sessions. *Builder call:* the mockup and this document are authoritative.
- Wording of the privacy draft and of error states not given above.
