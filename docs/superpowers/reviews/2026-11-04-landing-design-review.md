# Packet landing page: design review, round 1

Date: 2026-11-04
Reviewed: `feat/landing-site` at `02d06ba`, built with `npm run build` and served with `next start`, screenshotted with Playwright (Chromium) at 390×844, 768×1024, 1280×720, 1440×900 and 1920×1080.
Screenshots: `2026-11-04-landing-design-review/*.png`
Spec: `../specs/2026-10-26-packet-landing-design.md`
Status: findings and a tracker. Nothing here is implemented yet.

This review covers alignment, hierarchy and placement on `/` only. It also records a cold read of the page: what a visitor with no idea what Packet is sees first, and what the site feels geared toward.

---

## 1. Principles this review applies

Short, so the findings below can cite them by name.

**Hierarchy.** The order in which the eye lands on things is set by size, weight, contrast, colour, position and the space around an element. A page should have one dominant element per screen and a ladder of sizes with consistent steps, so that bigger always means more important. The quick test is the squint test: blur the page and see what survives. What survives is what the page is actually saying. ([NN/g, Visual hierarchy](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/); [NN/g, Five principles of visual design](https://www.nngroup.com/articles/principles-visual-design/))

**Scanning.** On text-heavy pages people scan in an F: across the top, then down the left edge. On sparse marketing pages with a figure they move in a Z or a "layer cake", reading headings and skipping body. Either way the first fixation goes to the largest, highest-contrast or moving thing, and the top-left anchors the read. Motion pulls attention before type does. ([NN/g, F-shaped pattern](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/); [F and Z patterns on landing pages](https://www.wordstream.com/blog/ws/2018/07/31/f-z-patterns-landing-page-design))

**The first screen.** Everyone scrolls, but the first screen decides whether they do. It has to answer, in order: what is this, is it for me, what do I do next. A call to action is read in the light of the value statement next to it; without that statement it is a button asking for effort with no reason given. ([NN/g, The fold manifesto](https://www.nngroup.com/articles/page-fold-manifesto/); [Smart Insights on CTA placement](https://www.smartinsights.com/conversion-optimisation/landing-page-optimisation/where-is-the-best-place-to-put-your-cta/))

**Alignment.** One left edge for the whole page. Items in a row share a baseline, or a bottom edge for controls. Columns that sit beside each other share a top. Use optical alignment for shapes (marks, circles, arrows) and geometric alignment for text. Every edge that almost lines up with another edge reads as a mistake.

**Proximity and grouping.** Things that belong together sit close, things that do not sit apart. The space inside a group must be visibly smaller than the space between groups. When a control, a message or a link is missed although it is on screen, it is usually too far from the thing it belongs to. ([NN/g, Proximity principle](https://www.nngroup.com/articles/gestalt-proximity/); [NN/g, Visual design glossary](https://www.nngroup.com/articles/visual-design-cheat-sheet/))

**Placement of controls.** Put controls next to what they control. Make the targets large and close (Fitts). Offer few choices at once (Hick). Repeat the main action about every one and a half screens on a long page. ([Laws of UX](https://lawsofux.com/); [Fitts's law](https://lawsofux.com/fittss-law/))

**Rhythm.** Sections should have a consistent beat: the same gap between sections, a smaller and consistent gap from a heading to its content, and the same column structure from one section to the next, so a change in structure means something.

**Feedback.** A state change has to look different, not only read different. Errors need a visual mark (colour, weight or an icon) distinct from hints. A focus style should belong to the component it sits on.

---

## 2. Cold read: a visitor who has never heard of Packet

### 2.1 Where the eye goes

Desktop, 1440×900 (`fold-1440x900.png`, `squint-1440x900.png`):

1. **"Packet"** at 130px, top left. The largest thing on the page by a factor of three.
2. **The globe.** It is the biggest mass on screen and it drifts, so it wins the second fixation and keeps pulling the eye back. In the squint test the page is the word and the sphere; nothing else survives.
3. **The black "Check" button.** The only solid dark block.
4. **"Is Packet coming to your street?"** Read last, and only because it sits between the name and the button. At 18px bold it is one pixel bigger than body text.
5. The nav, if at all.

The lower half of the screen is empty. Nothing below the field hints that the page continues.

Phone, 390×844 (`fold-390x844.png`, `squint-390x844.png`):

1. **The globe**, which fills the top 300px (36% of the screen) before anything else.
2. **"Packet"** a third of the way down.
3. **The "Check" button**, then the question.
4. The leading lines and the first words of "Delivery from U Village shops to homes nearby." at the very bottom edge.

On the phone the page does explain itself in the first screen, but only because the next section's heading peeks in at the bottom.

### 2.2 What the visitor learns in the first five seconds

On every desktop size the first screen says: a thing called Packet, a globe, "is it coming to your street?", a field for an address. It never says what Packet is. The line that does ("Delivery from U Village shops to homes nearby.") starts at y=958 on a 900px-tall viewport, y=804 on a 720px one, and only its top edge shows at 1920×1080 (`fold-1280x720.png`).

That matters more than it looks, because the shape of this first screen is an existing pattern: a name, "coming to your street?", an address check, a map. That is the fibre-internet availability page. The name "Packet" reinforces it. A visitor arriving from a friend's text with no context is as likely to read this as an ISP roll-out as a delivery service. A visitor from a flyer already knows and is fine.

The spec's own goal (§1: "explain what Packet is and how it works, so a visitor understands it in one screen") is not met on desktop and is met by accident on phones.

### 2.3 What the site feels geared toward

The visual language is confident and consistent: halftone cartography, crop marks, dimension lines, a station-sign button, condensed caps labels, hand-wobbled technical drawings. It reads as a design-literate hardware or infrastructure company. Something between a mapping firm and an aerospace startup. It does the one thing the spec most wants: it does not read as a class project.

What it does not yet read as is "lunch to your door". Every figure above the Mission section is abstract (a dotted sphere, a dotted route, a tunnel of marks). The first concrete object on the page is the aircraft drawing, about 2,200px down. There is no shop, no bag, no door, no person. The copy is warm ("your street", "your door", "bring it in when you're ready") but the pictures are cool, and pictures are read first. The audience in §1 is students and neighbours who want things delivered. The site currently feels made for people who appreciate precision, and asks them to trust that food is involved.

This is not a call to change the language. The restraint is the brand and it is working. It is a call to put one plain descriptor line and, ideally, one concrete sketch in the first screen so the precision has an obvious subject.

---

## 3. Findings

Severity: **High** hurts the page's goal (understand, check, sign up). **Medium** is a visible flaw a designer would fix before showing it. **Low** is polish.

Each item has an ID for the tracker in §4.

### 3.1 Hero and first screen

**H-01 · High · The first screen never says what Packet is.**
Principle: the first screen answers "what is this" before "what do I do". Observation: at 1280, 1440 and 1920 the fold contains the name, the question, the field and the globe; the descriptor is below the fold (§2.2). Suggestion: one line under the wordmark and above the question, in the 20px lead size: "Delivery from U Village shops to homes nearby, by autonomous aircraft." (the `<meta description>` already says this). The question then stays as the form's own label. If that line moves up, the What section's heading can shrink to the leading lines and the paragraph, or the two can merge (see W-01).

**H-02 · High · The hero reserves 86vh and uses about 40% of it.**
Principle: whitespace must be intentional; an empty half-screen reads as "the page ended". Observation: content ends at y≈383 while the hero runs to y=838 at 1440×900; on a 768×1024 tablet it is 550px of nothing beside a sliver of globe (`fold-768x1024.png`). Suggestion: either size the hero to its content plus the globe (for example `min-height: clamp(520px, 72vh, 760px)`) so the next heading rises into the fold, or fill the space with H-01's descriptor and a scroll cue. The globe's radius is tied to the hero height, so check it after resizing.

**H-03 · Medium · The question is the page's main ask and is set one pixel above body.**
Principle: a ladder of sizes with consistent steps. Observation: h1 130px → question 18px → body 17px. The 7:1 drop means the eye goes name → button and skips the words that give the button its meaning. Suggestion: set the question and the result lines ("That's inside the first area…", "You're on the list.") at 24–26px, or make them the hero's h2. Keep them Atkinson bold.

**H-04 · Medium · On phones the globe comes before the name.**
Principle: top-left anchors the read; the first 60% of a phone screen should carry name, descriptor and action. Observation: 300px of dots, then "Packet" at y=380, the button at y=508. Suggestion: 200–220px for the globe, or move it behind the top-right of the wordmark as a partial sphere bleeding off the right edge, so name, line and form sit in the top 60%.

**H-05 · Medium · Between 761px and about 1000px the globe is a fragment.**
Observation: the 440px copy column plus the 40px gap and the 160px fade leave the sphere a thin crescent on the right (`fold-768x1024.png`). Suggestion: use the stacked (phone) layout up to about 900px, or let the globe sit lower and lighter under the copy in that range.

**H-06 · Medium · After a check, the button sits above the field.**
Principle: controls in a row share a bottom edge. Observation: in the email step the "Get updates" button is top-aligned with the "EMAIL" label; its bottom is about 27px above the field's underline (`hero-inside-1440x900.png`). The same happens in the closing form (`section-cta-h-1440x900.png`). Cause: `.sign { align-self: flex-start }` in `globals.css` overrides the row's `items-end`; it only looks right in the address step because that label is visually hidden. Suggestion: drop `align-self` from `.sign` and let the row align it, or set `align-self: flex-end` on the button inside form rows.

**H-07 · Medium · Errors look like hints.**
Principle: a state change has to look different. Observation: "Enter a street address or cross streets." and "We couldn't find that address…" are 17px regular ink, identical to "Get an email when Packet launches." (`hero-notfound-1440x900.png`). `aria-invalid` is set but nothing styles it. Suggestion: errors in Packet Red, and a 2px red underline on the invalid field (`input[aria-invalid="true"]`). Hints stay ink.

**H-08 · Low · The focus ring boxes an underline field.**
Observation: a 2px rectangular outline with a 3px offset around an input whose only edge is a bottom rule makes the focused field look like a different component. Suggestion: on focus, thicken the underline to 2.5–3px and keep the rectangular ring for buttons and links.

**H-09 · Low · The "inside" result has no reward.**
Observation: the result line has the same size and weight as the question; the globe's marks are the only signal and they are off to the right. The one mustard tag the rules allow per screen is unused on `/`. Option: a small mustard tag beside the result ("IN THE FIRST AREA"). Judgment call; H-03 may be enough.

**H-10 · Low · The done state leaves the hero empty.**
Observation: "You're on the list." and one text link. Suggestion: add the next thing to do under it ("See how it works" to `#how`, or "Products"), so the hero still has a direction after the task is done.

**H-11 · Low · The globe is centred in the hero, the copy is not.**
Observation: the sphere's top (y≈90) sits 70px above the wordmark's cap line (y≈160) and its bottom sits far below the form. Suggestion: align the sphere's top with the cap line, or accept it as a bleed and leave it. Low priority; revisit after H-02 changes the hero height.

### 3.2 What

**W-01 · Medium · The only section with no figure on the right.**
Principle: a consistent column structure, so a break in it means something. Observation: hero, Mission, Showcase and the closing CTA are copy-left, figure-right; What is copy-left, nothing-right, and 484px tall for about 230px of content. Suggestion: if H-01 moves the headline into the hero, cut this section to the lines and the paragraph with half the padding. If the headline stays, give the right side something concrete: one of the item sketches already built for Products (`ItemBowl`, `ItemCup`, `ItemWrap`) would also answer P-02.

**W-02 · Low · The leading lines read as a divider.**
Observation: placed between the h2 and the paragraph, full width, they separate the two. The rules say they are never a divider. Suggestion: put them above the h2 as the section's opener, or after the paragraph as its close, so they read as a signature rather than a rule.

**W-03 · Low · No lead paragraph here, but there is one in Mission.**
Observation: Mission opens with a 20px lead then 17px body; What goes straight from 44px to 17px. Suggestion: give What's paragraph the 20px lead size, or drop Mission's lead to 17px. One pattern.

### 3.3 How it works

**K-01 · Medium · Step titles barely outrank their text.**
Observation: 19px bold over 17px regular; the numbered circle does all the work. Suggestion: titles at 22px, or body at 16px within the steps. Keep the circle.

**K-02 · Low · 200px of canvas for a route that uses two thirds of the width, then a 300px gap.**
Suggestion: 160px canvas on desktop and tighter section padding (see P-01). The route already runs through the bullet centres, which is right; keep that.

**K-03 · Low · Three numbering styles in three adjacent sections.**
Observation: filled circles 1–3 here, Barlow "01 02 03" in the showcase, outlined callouts 1–4 in the drawing. Suggestion: the drawing's callouts are a convention of technical drawings and should stay; make the step bullets and the product numbers share one style (Barlow "01" would do, since the circles are small at 32px anyway).

### 3.4 Mission

**M-01 · Medium · The drawing's top sits 100px above the heading's top.**
Principle: columns beside each other share a top; every other h2 on the page starts at the top of its section. Observation: `items-center` on the 5/7 grid (`section-mission-h-1440x900.png`). Suggestion: `items-start`, with the drawing's top dimension line on the h2's cap line. If the drawing must stay centred, give it top padding equal to the h2's offset.

**M-02 · Medium · On phones the drawing's labels are illegible.**
Observation: plan and side views share about 340px; "SPAN [TBD]", "HEIGHT [TBD]", "PLAN", "SIDE" and the callout numbers come out at roughly 6–7px (`section-mission-h-390x844.png`). Suggestion: stack plan above side under 760px, or show only the side view on phones and keep both on `/products`.

### 3.5 Showcase

**S-01 · High · Product names are the second-largest type on the page.**
Principle: bigger means more important; the ladder has to hold across sections. Observation: h3 at 72px above every h2 at 44px. Skimming, "Vehicle 01", "Packet for iPhone" and "Dispatch" outrank "Delivery from U Village shops to homes nearby." (`full-1440x900.png`). The spec asks for them "set like a hero", which is why, but the page then has four heroes. Suggestion: `clamp(36px, 4vw, 56px)` for the product name so it sits one step above the h2s, not two, and let the drawing carry the scale. If the names must stay 72px, demote the section heading to a Barlow label ("PRODUCTS") so each section has exactly one big thing.

**S-02 · Medium · The section heading is orphaned above the slide.**
Observation: the copy is vertically centred in a 540px stage, leaving about 170px between the h2 and the "02" label (`section-system-h-1440x900.png`). Suggestion: align the slide copy to the top of the stage with 32–48px of padding, so h2 → number → name read as one column.

**S-03 · Medium · Three controls in three places, and the tabs look like a loading bar.**
Principle: controls near what they control, grouped. Observation: progress tabs and pause at bottom-left, "Next" with the arrow at bottom-right inside the stage, "About…" in the copy. The tabs are 44×4px bars with no label; filled-black reads as a progress indicator, not a button. Suggestion: one control row under the stage, left-aligned to the margin: the three tabs with their Barlow numbers ("01 02 03") above the bars, then pause, then the Next arrow with the next name. The peek can stay in the corner as a figure.

**S-04 · Low · The Next arrow overlaps the peek drawing.**
Observation: the 56px circle sits on the dispatch grid's dotted lines on desktop; on phones a grey square and a few dots poke in at the right edge and read as a glitch (`showcase-02-390x844.png`). Suggestion: push the peek further off-screen (translate 60% instead of 45%), and hide it under 760px.

### 3.6 Closing call to action

**C-01 · Medium · Same button misalignment as H-06.**
Observation: "Get updates" is top-aligned with the "EMAIL" label; its bottom is 25px above the field's underline (`section-cta-h-1440x900.png`). Same fix.

**C-02 · Low · The App Store line floats.**
Observation: "Packet for iPhone is coming to the App Store [LAUNCH DATE]." sits about 80px under the form at 14px, tied to nothing. Suggestion: 16–24px under the form's message line, or move it into the footer next to the copyright.

**C-03 · Low · On phones the tunnel comes straight after the showcase controls.**
Observation: 300px of scattered marks begin about 60px under the tabs and read as showcase debris. Suggestion: more top padding before the tunnel on phones, or put the tunnel after the heading on phones so the heading marks the boundary.

**C-04 · Low · The two sign-up forms wrap differently on phones.**
Observation: the hero's address row fits on one line (field 213px + 16px + "Check" 110px = 339px); the email rows need about 366px because "Get updates" is wider, so the button drops to its own line. Suggestion: decide once. Either both rows stack on phones (field full width, button under it) or the email button narrows. Stacked is the better phone pattern.

### 3.7 Footer and nav

**F-01 · Low · Emblem edge.**
Observation: the crop marks start about 3px inside the margin and the wordmark 27px inside it, while the copyright line starts on the margin. The emblem is one unit, so this is acceptable; noting it so it is a decision rather than an accident.

**N-01 · Low · "Get updates" in the nav duplicates the form on the same screen.**
Harmless on `/`; it is there for the subpages. Leave it unless the nav gets crowded.

### 3.8 Page-wide

**P-01 · Medium · Section padding doubles up.**
Observation: 120px top and 120px bottom on every section, plus 48px inside, gives 250–300px of white between content blocks; the page is 4,529px tall with content in about half of it (`full-1440x900.png`). Suggestion: 88–96px on desktop and 56–64px on phones, and a fixed 40–48px from an h2 to its content, so inside-a-section is visibly tighter than between-sections. Keep the hero's generosity as the deliberate exception.

**P-02 · Medium · Nothing concrete above the aircraft.**
Observation: the three figures before Mission are a dotted sphere, a dotted route and a tunnel of marks (§2.3). Suggestion: one concrete sketch early. The item drawings built for Products (a bowl, a cup, a wrap) in the hero's lower-left space or beside the What paragraph would say "food" without a photo and without breaking the drawing rule.

**P-03 · Medium · The type ladder has a step out of order and three sizes doing one job.**
Observation: 130 (h1) · 72 (product name) · 44 (h2) · 20 (lead) · 19 (step title) · 18 (hero question) · 17 (body) · 15 (nav, links) · 14 (captions) · 12 (labels). Suggestion: 130 · 56 · 44 · 24 · 17 · 15 · 12, with 24 doing lead, hero question and step title.

---

## 4. Tracker

| ID | Sev | Area | Finding | Status |
|---|---|---|---|---|
| H-01 | High | Hero | First screen does not say what Packet is | open |
| H-02 | High | Hero | Hero height leaves lower half empty | open |
| S-01 | High | Showcase | Product names outrank section headings | open |
| H-03 | Med | Hero | Question is 18px, one step above body | open |
| H-04 | Med | Hero | Globe before the name on phones | open |
| H-05 | Med | Hero | Globe is a fragment at 761–1000px | open |
| H-06 | Med | Hero | Button above field in the email step (`align-self`) | open |
| H-07 | Med | Hero | Errors styled like hints | open |
| W-01 | Med | What | Only section with no figure; 484px for 230px of content | open |
| K-01 | Med | How | Step titles 19px over 17px body | open |
| M-01 | Med | Mission | Drawing top above heading top | open |
| M-02 | Med | Mission | Drawing labels illegible on phones | open |
| S-02 | Med | Showcase | Heading orphaned 170px above slide | open |
| S-03 | Med | Showcase | Controls scattered; tabs look like a loading bar | open |
| C-01 | Med | CTA | Button above field (same as H-06) | open |
| P-01 | Med | Page | Section padding doubles up | open |
| P-02 | Med | Page | Nothing concrete above the aircraft | open |
| P-03 | Med | Page | Type ladder out of order | open |
| H-08 | Low | Hero | Focus ring boxes the underline field | open |
| H-09 | Low | Hero | "Inside" result has no reward | open |
| H-10 | Low | Hero | Done state is empty | open |
| H-11 | Low | Hero | Globe and copy do not share a top | open |
| W-02 | Low | What | Leading lines read as a divider | open |
| W-03 | Low | What | No lead paragraph here, one in Mission | open |
| K-02 | Low | How | Canvas height and gap | open |
| K-03 | Low | How | Three numbering styles | open |
| S-04 | Low | Showcase | Next arrow overlaps the peek; peek is a glitch on phones | open |
| C-02 | Low | CTA | App Store line floats | open |
| C-03 | Low | CTA | Tunnel right after showcase controls on phones | open |
| C-04 | Low | CTA | Forms wrap differently on phones | open |
| F-01 | Low | Footer | Emblem edge inside the margin | open |
| N-01 | Low | Nav | "Get updates" duplicates the form on `/` | open |

Suggested order of work: H-06/C-01 (one CSS line, visible everywhere), then H-01, H-02 and H-03 together as one hero pass, then S-01 to S-03 as one showcase pass, then P-01 and P-03 as a spacing and type pass, then the rest.

---

## 5. Notes

**Decisions already made in the spec, not reopened here.** A marquee band and a visible carousel track in the showcase (rejected). A square or icon at the centre of the tunnel (rejected). A ZIP field (replaced by the address field). The App Store line in the hero (dropped in `11c661d`). The university named in the service-area copy (dropped). Dark mode (out of scope). Photographs of the aircraft (never; drawings only).

**What was not reviewed.** `/products`, `/press` and `/privacy`. The address check against the real geocoder (the hero-state screenshots used a mocked `/api/check`). Motion timing. Keyboard and screen-reader behaviour beyond what the markup shows.

**Screenshot method.** Playwright, device scale factor 1, no reduced-motion preference, 1.2s settle after `networkidle`. Section screenshots scroll each `h2` to 96px from the top. The squint images apply `filter: blur(7px) grayscale(1)` to `<html>`. In full-page captures the Mission drawing is missing because its draw-in is scroll-triggered and the capture does not scroll; that is a capture artifact, not a page bug.
