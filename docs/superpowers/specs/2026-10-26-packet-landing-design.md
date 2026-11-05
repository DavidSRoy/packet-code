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

Inks (exactly four, as CSS tokens): Packet Red `#B4432F`, Black `#111111`, Mustard `#D3A13F`, White `#FFFFFF`. No other neutral is used; the showcase progress track that needed one is gone (§6.11).

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
- Left: h1 "Packet" (Libre Franklin 600, `clamp(64px, 9vw, 136px)`). Under it, the premise line, 22px Atkinson, at most 28ch wide: "Autonomous delivery, from nearby shops to your door." Under that, the sign-up form in two steps that share one slot:
  1. "Is Packet coming to your street?" One field, labeled "Street address or cross streets" for screen readers only (no visible label), with placeholder "NE 45th St and 25th Ave NE", and a station-sign button, "Check".
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
- Right (beside the copy, bleeding off the right edge): a canvas **halftone globe**. The street grid around U Village is drawn as dots on a sphere, tilted (`roll -0.5`), small enough that the rim shows, over a faint latitude and longitude grid so the sphere reads where there are no streets. The art fades out before the copy column instead of ending on a straight cut. It drifts slowly.
  - On a check, the globe turns so the found point lands on the globe's front face, and four corner marks close in on it. The service-area boundary is drawn on the globe as a dotted outline, so inside and outside are visible.
  - The anchor-solving approach is in the mockup's `aim()` function.
  - Use real U Village streets (§6.12).
- Under 900px the globe sits above the copy, centred: 220px tall on phones and up to 320px on tablets (`clamp(220px, 42vw, 320px)`).
- The hero is `min-height: clamp(520px, 72vh, 760px)`, so the next heading rises into the first screen on desktop.
- The question and result lines are 24px Atkinson bold. Errors are set in Packet Red and the invalid field's underline turns red; hints stay black. Focus thickens a field's underline to 3px instead of drawing a box around it.
- The button sits on the field's bottom edge. On phones each form row stacks: the field full width, the button under it. The same holds for the closing form (§6.9).
- On load, the globe fades in (1.4s); then the wordmark, the premise and the form rise in turn (at 0.8s, 1.25s and 1.6s). Under reduced motion everything is shown at once.
- *Revised 2026-11-04 (hero pass; copy signed off by Tanner). Revised 2026-11-05: the intro sequence.*

### 6.2 What you can get
- h2 "Lunch, coffee, and anything in-between."
- The leading lines (this page's one use of them).
- Lead, 20px: "Whatever a shop near you sells, Packet can bring it to you wherever you are."
- Four item cards (two columns on phones), each a sketched drawing, the name and its kind: U Village Bowl / Lunch, Drumstick Wrap / Lunch, Cold Brew / Coffee, Anything that fits / In-between. The data lives in one typed array (`landing-items.ts`). Shops and prices stay on Products until they are real.
- A smaller line, 14px, under the cards: "Packet starts in University Village and the streets around it, including the U District and Bryant." The first area is named once on the page before the map.

### 6.3 Where Packet flies first (scroll-locked)
- Left: the **plan of the first area**, a flat projection of the baked streets (§6.12) in a 640 by 460 sheet: dotted streets (main darker than minor), the service-area boundary, the red block inside its corner marks at the U Village hub, a north arrow, and the places named in Barlow caps on white: University Village, U District, UW north campus, Bryant, Mercer Court inside the area; Ravenna and Laurelhurst outside it, fainter. Caption: "First area" and "Sheet 1". No pen filter on the plan, so it repaints cheaply while pinned.
- Right: h2 "Where Packet flies first." Then: "Packet is running in the university area first. The first flights cover University Village, the U District, Bryant, Mercer Court and the north campus." Then: "The streets around them come next, and the map grows as each one is added." Then the text link "Check your street" with an up arrow, to `#updates` (it sends the reader back to the hero form).
- The lock, 2.4 screens: the boundary draws itself (0.04 to 0.42); the hub's block fades in and its corner marks close in from three times their size (0.3 to 0.58); the five first-area places name themselves in that order (0.5 to 0.8); the second paragraph and the link rise last (0.84 to 0.93).
- Under 900px the plan sits above the copy. On phones the labels shrink to 11px and the two places outside the area are hidden.

### 6.4 How it works
- h2 "Four steps, all in the app."
- A scroll-driven canvas: the red block inside its corner marks travels a dotted route past the steps, climbing a little at each stop and leaving a mustard trail. The numbered bullets fill as it passes each one. The route takes its stops from the bullets' positions; when they stack (two columns under 760px, one under 480px) it spaces them evenly instead.
- Steps, each a 22px title and one line:
  1. Order: "Pick from a nearby shop's menu and pay in the app."
  2. Pick your spot: "A front step, a yard or a balcony with open sky above it. Packet remembers it."
  3. Follow it: "See each step as it happens, with the time it will arrive."
  4. At your door: "It's set down at your spot. Bring it in when you're ready."

### 6.5 Delivery (scroll-locked)
- The section is about the delivery, not the vehicle. The aircraft is the first product and gets its own section after this one (§6.6) and Products (§7). *Tanner's call, 2026-11-04.*
- Left: h2 "Autonomous delivery, built around the way you live." Three benefits, each a 22px title and one line:
  1. "Minutes, not an hour." "From the shop to your door, straight over the street."
  2. "Nothing on your street." "No car, no bike, no double-parking. One aircraft above it."
  3. "Set down, not handed off." "Left at your spot. Bring it in when you're ready."
  Then: "Vehicle 01 is the first step: a four-rotor aircraft that flies an order from the shop to your door."
- Right: the sketched **delivery drawing**, a side elevation from A to B:
  - the shop at A (awning, sign band, door, window) and a house at B (gable, door, window) on one ground line;
  - the route, mustard dots, rising from the shop's roof, running level above the street and setting down at the doorstep;
  - the package in transit, the red block inside four corner marks, as on the route in How it works;
  - a mustard landing pad at the doorstep;
  - an altitude dimension line and an A-to-B dimension line, labelled "Altitude" and "A to B" with no values (the drawing is a demonstration, not to scale; *Tanner, 2026-11-04*);
  - labels "A · Shop" and "B · Your door" under the ground line; "Not to scale." under the drawing. No callouts and no legend: the benefits beside it do that work.
- The lines draw in once (stroke-dashoffset) when the figure enters; the route and the package fade in after them.
- The lock, 3 screens: the package rests at the shop, lifts off and crosses above the street (0.06 to 0.86 of the lock, along the route itself), and sets down on the pad. Benefit 1 arrives as it lifts off (0.12), 2 as it crosses the street (0.38), 3 and the pad as it comes down (0.64), and the Vehicle 01 line once it has landed (0.86).
- No aircraft appears in this drawing. Under 900px the drawing sits above the copy. The Vehicle 01 plan-and-side drawing from the first build (`VehiclePlanSide`) is kept for Products.

### 6.6 The first product
- A 1.5px rule above. Left: the label "01", h2 "The first product: Vehicle 01.", the product's description from Products, then a three-row spec table (Barlow keys, hairline rows) with the facts the team has given: Capacity "Up to 15 lb", Flight time "45 minutes", Built for "City and local deliveries". Rows still marked to follow stay on Products only.
- Two text links: "About Vehicle 01" to `/products#vehicle-01` and "See the app and Dispatch" to `/products`.
- Right: the aircraft's side drawing (`VehicleSide`). Under 760px it sits below the copy.
- The product showcase from the first build (one product at a time, auto-advance, tabs, pause) is removed. The app and Dispatch are reached through the link.

### 6.7 What's next
- h2 "What's next."
- Four stops on a dotted mustard route that runs off the right edge: the red block inside its corner marks at the first, numbered circles at the rest. Each has a Barlow label and a 20px line: Now "Sign-ups open"; Next "First test flights"; Then "First deliveries in the university area"; After "More of Seattle".
- Under 760px the route turns vertical and the stops stack beside it.

### 6.8 Questions
- h2 "Questions a neighbor would ask." Lead, 20px: "Packet flies over streets people live on. These are the questions we would ask, and the answers as they stand."
- Seven collapsible rows (`<details>`), numbered 1.0 to 7.0 like the Press manual, 1.5px rules between them, a plus at the right that becomes a minus. The first row starts open. Where the browser supports it the answer's height animates; elsewhere it opens at once.
  1. "Is it safe?" "Vehicle 01 flies under the FAA's rules for small unmanned aircraft, on routes Dispatch plans in advance and follows from pickup to drop-off."
  2. "How loud is it?" "It is overhead for seconds, not minutes. We will publish noise measurements before the first flight."
  3. "Where does it land?" "At the spot you chose in the app, with open sky above it. It sets the order down and leaves."
  4. "What if I'm not home?" "It is left at your spot, like a package. The app shows you when it arrived."
  5. "What about rain and wind?" "Flights pause in heavy rain and high wind. The app says so before you order."
  6. "Does it record my street?" "The aircraft uses its sensors to fly and to land at your spot. Packet does not sell data, and the privacy page says what is kept."
  7. "Who is flying it?" "Packet's own team in Seattle, with Dispatch watching every flight."
- The data lives in one typed array (`questions.ts`). **Tanner to confirm** each answer before the site is promoted.

### 6.9 Closing piece: the call to action and the footer in one frame (scroll-locked)
- One full-screen stage with four crop-mark corners, like the emblem's, at its corners. Behind it the **crop-mark tunnel**, a canvas of dotted corner marks rushing toward a vanishing point (rings at `D0·q^(i+f)`, a slight twist per ring, fading near the center), masked so it is faint under the copy and full on the right. **No square or icon at the center.**
- Left, centred: h2 "Hear when Packet reaches your street." An email field and "Get updates" (this screen's one station-sign button). Then: "Sign up now and you will be first in line when Packet reaches your street." Then: "Know a neighbor who would want this? Send them the link." Then, 14px: "Packet for iPhone is coming to the App Store."
- This form has no address step. It posts with only the email, so `in_area` is null.
- The footer sits inside the same frame, at the bottom: the emblem, "© [YEAR] Packet. Seattle, Washington.", the line "For shops  Run a shop near U Village? Get in touch." (linking to the Press contact section), and the links Products, Press, Privacy at the right. The other pages render the footer on its own, as before.
- The lock, 1.8 screens: the tunnel grows toward the reader (scale 0.55 to 1) and the copy rises (0.15 to 0.5), then the footer (0.45 to 0.75).

### 6.10 Scroll-locked sections: how they work
- A locked section is `--screens` viewports tall; its stage sticks to the top (`position: sticky`, `100svh`) while the reader scrolls through, and the section's `--p` custom property runs 0 to 1 over that distance (`useLockProgress`, one scroll listener per section, `requestAnimationFrame`). Everything that moves is CSS from `--p`: a ramp `--t` runs 0 to 1 while `--p` crosses `[--a, --b]`, and `.rise` elements fade and lift with it. The one thing CSS cannot do, moving the package along the route, uses `getPointAtLength` from the same value.
- The CSS default is `--p: 1`, the end state, so the page is complete before JavaScript runs and without it.
- Under reduced motion nothing pins and `--p` stays at 1. When the stage's content would not fit the viewport (small phones with large text), nothing pins either; `--p` then runs 0 to 1 as the section scrolls into view, so the same motion plays, unpinned.

### 6.11 Removed from the mockup for the build
- The "Working notes" disclosure.
- The product showcase (§6.6) and the first build's "What" and "Mission" sections, replaced by §6.2, §6.5 and §6.6.

### 6.12 Real streets in the globe
Replace the stylized grid with U Village area streets, a simplified set of main and minor streets, from OpenStreetMap data.
- Bake it into a small static JSON at build time or by a one-off script committed with its output.
- Keep ODbL attribution in the footer or on `/privacy`.
- Main streets render darker than minor ones.

## 7. Products page

See `products-1440.png`.

- Intro: h1 "Products". Lead: "Three parts that take an order from a U Village shop to your door."
- Three product sections, in the order 01 to 03, alternating copy and drawing sides. Each has the number, h2 name, two sentences and a spec table (Barlow keys, hairline rows).
  - **Vehicle 01**: Capacity "Up to 15 lb"; Flight time "45 minutes"; Built for "City and local deliveries" (*from Tanner, 2026-11-05; the Rotors row was dropped the same day*); Cruise speed, Flight altitude and Weather limits `[TBD]`.
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

- 0.2 "Never show the drone" becomes: the aircraft appears only as a technical drawing (Products, Press and the landing page's first-product section). The landing page's delivery section shows the delivery, not the aircraft.
- Scroll-locked sections (§6.10): three on the landing page, each with a reduced-motion path and a no-JavaScript end state.
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

The address text is never stored or logged. A repeat sign-up with the same email upserts: it fills fields that are still empty, keeps every value already stored (first touch wins, so the flyer that first brought someone in keeps the credit and nobody who knows an email can rewrite its row), keeps `created_at`, and bumps `updated_at`.

### 10.2 Endpoints

Both are route handlers in `landing/src/app/api/`. Both use one shared server function, `checkAddress(q)`, which:
- resolves a cross street ("NE 45th St and Brooklyn Ave NE") from the server-only OSM intersections table, and geocodes the query only when that finds nothing;
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
- a 6s timeout.

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
- the remaining Vehicle 01 specs (speed, altitude, weather, dimensions);
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
  - **Repeat sign-up**: the same email upserts and doesn't duplicate. It fills only fields that are still empty and keeps the values already stored.
  - **Closing form**: stores a row with null `in_area`.
  - **Bad input**: posting it directly to the API returns 400.
  - **Scroll-locked sections**: the plan draws and names its places, the package travels the route and lands, the closing frame arrives; each unpins at its end. The About and "See the app and Dispatch" links land on the right places on `/products`.
  - **Questions**: rows open and close with the pointer and the keyboard.
  - **Reduced motion**: nothing moves on its own and nothing pins; every section shows its end state.
- Screenshots at 375, 430, 768, 1280, 1440 and 1920 for `/`, `/products` and `/press`:
  - no horizontal scroll, nothing clipped;
  - compared against the reference images in this folder.
- Keyboard: every control is reachable with visible focus, the question rows included.

## 16. Left to the builder

- Component breakdown and file layout under `landing/src`, within the house rules.
- How the canvas pieces (globe, trip, tunnel) share the halftone and corner-mark helpers.
- The exact OSM extraction and simplification approach for streets.
  - *Builder call:* a one-off script in `landing/scripts/` queries Overpass (network allowed) for roughly 2.5 km around U Village, enough to show the boundary with streets beyond it. It simplifies the result, commits it as `src/data/streets.json`, and the script is committed alongside it.
- Cross-route "Get updates" focus. *Builder call:* on `/` the page reads `#updates` on load and on `hashchange`, scrolls to the hero and focuses the address field.
- The Figma file needs authorization in build sessions. *Builder call:* the mockup and this document are authoritative.
- Wording of the privacy draft and of error states not given above.
