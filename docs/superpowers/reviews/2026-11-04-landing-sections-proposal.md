# Packet landing page: section proposal

Date: 2026-11-04
Builds on: `2026-11-04-landing-design-review.md` (alignment, hierarchy, placement). This document is about content: what the page says and shows, section by section.
Status: proposal. Nothing here is built. The copy drafts use `[BRACKETS]` only where a fact cannot be worded generically yet, per spec §14.
Revised 2026-11-04 after Tanner's review of the mockup (the Packet Landing Mockup canvas): no proof strip in the hero; an intro sequence; the items copy, with the first-area line as a smaller disclaimer; the map section as plain text about the university area; an up arrow on "Check your street"; the route given headroom so the package is not clipped; generic wording in place of placeholders wherever generic wording still works.
Page with the current-state gallery: Packet Landing Sections artifact (private; shared from its page).

## 1. The problem

The page is seven blocks, and every block is a heading and one sentence. After the hero, a visitor learns: delivery from nearby shops; three steps in an app; a promise about speed and streets; three product names; an email form. Nothing on the page says what you can get, how long it takes, what it costs, what hours it runs, where exactly it flies, whether it is safe or loud, what happens if you are not home, or who is behind it. The second half is about the company's system, not the visitor's lunch.

Three things make it feel hollow:

1. **No concrete value.** Every specific is a placeholder or missing. A pre-launch page can still be specific about the first area, the first shops, the launch date and what the first deliveries will be.
2. **No answers to the obvious doubts.** An aircraft over a residential street raises noise, safety, privacy, weather and landing questions before anyone cares about speed. The page is silent on all of them. Wing's homepage leads its news with "being a good neighbor"; Manna links a safety page and a community guide; Zipline keeps a safety page in its footer.
3. **No proof and no people.** No map a neighbour recognises, no shops named, no team, no timeline, no reason to sign up today rather than later.

## 2. What strong pages do

From the three operating drone-delivery companies' homepages (fetched 2026-11-04) and current landing-page guidance:

| Pattern | Wing | Zipline | Manna | Packet today |
|---|---|---|---|---|
| Promise in the hero, one CTA | "Delivery, elevated." Get delivery | "Look up." Try it now | "Time flies." Get some air | Yes |
| Speed stated | 2 min 47 s fastest | 86 s fastest, "minutes" | "about 3 minutes" | No |
| What you can get | Partners, essentials | Use cases: meals, medicine, essentials | Ten item images, "If it fits it flies" | No (exists on /products) |
| How it works, 3 steps | Shop, pick your spot, get delivery | Pick, watch it fly, get it | Order, look up, pick up | Yes, 3 steps, no spot |
| Where it operates | Address checker, Locations | Not stated | "Where we fly": live, next, soon | Address check only |
| Benefits | Fast, Convenient, Eco friendly | Fresher, Worry-free, Less waiting | Cuts traffic, less pollution, supports local, minutes | One sentence |
| Proof | Testimonial, 1M+ deliveries | Testimonial, 75,000 lives, 0 emissions | Partner logos | None (pre-launch) |
| Trust | "Good neighbor" story | Safety page | Safety, regulation, community pages | None |
| News | 4 stories | 4 stories | none | On /press only |
| Closing CTA | Yes | Yes | Yes | Yes |

Landing-page guidance converges on the same order: a specific, outcome-driven headline with one call to action; proof near the conversion points; problem then solution; benefits over specifications; trust signals and an FAQ for objections; the offer; the CTA repeated at the bottom. Pre-launch pages add a launch date, a reason to sign up now, a referral mechanic and source tracking (which Packet already has).

## 3. Proposed structure

Eleven blocks instead of seven. Each adds one thing a visitor did not have. Order follows the visitor's questions: what is it, what do I get, is it for my street, how does it work, why is it better, what is the vehicle, who are you, when, is it safe, sign up. (*Revised 2026-11-05: the questions moved to the bottom, just before the closing, at Tanner's request.*)

### A. Hero (keep) plus an intro sequence
The hero stays as built, with no proof strip (Tanner, 2026-11-04: those facts do not earn their place). Add an intro: the globe appears first, then the wordmark, then the premise line and the form, about two seconds in all. Under reduced motion everything shows at once.

### B. What you can get (replaces "What")
- h2 "Lunch, coffee, and anything in-between."
- Lead: "Whatever a shop near you sells, Packet can bring it to you wherever you are."
- Figure: the four item sketches already built for Products (bowl, wrap, cup, box) in a row, each with a one-word kind under its name (Lunch, Lunch, Coffee, In-between) until shops and prices are real. The leading lines sit under the h2, their one use on the page.
- A smaller disclaimer line after the lead: "Packet starts in University Village and the streets around it, including the U District and Bryant."
- Reference: Manna's item grid; Zipline's use-case panels.

### C. Where Packet flies first (new)
- h2 "Where Packet flies first."
- Figure: a plan map of the first area as a technical drawing. Dotted streets from `streets.json`, the service-area boundary from `service-area.ts` as a dashed line, the red block at the U Village hub, labels for University Village, the U District, Bryant, Mercer Court and the UW north campus, a north arrow.
- Beside it, plain text, no placeholders: "Packet is running in the university area first. The first flights cover University Village, the U District, Bryant, Mercer Court and the north campus. The streets around them come next, and the map grows as each one is added." A text link "Check your street" with an up arrow returns to the hero form (one station-sign button per screen).
- This is the section a neighbour recognises. The globe is atmosphere; this is a map.

### D. How it works (keep, add the spot)
Four steps instead of three: **Order** · **Pick your spot** · **Follow it** · **At your door**. Step 1: "Pick from a nearby shop's menu and pay in the app." New step 2: "A front step, a yard or a balcony with open sky above it. Packet remembers it." Wing's second step; it answers the landing question before the FAQ does. The route animation gets a fourth stop, with headroom so the package and its marks are not clipped.

### E. Why (Mission, as benefits), scroll-locked
Keep the h2 and the delivery drawing, and lock the section (§5): the package travels the route as the visitor scrolls, and the three benefits arrive one by one. The callouts and legend come off the drawing here; the benefits do their job. Replace the lead and body with three benefits, each one line:
1. **Minutes, not an hour.** From the shop to your door in about [TBD] minutes.
2. **Nothing on your street.** No car, no bike, no double-parking. One aircraft above it.
3. **Set down, not handed off.** Left at your spot. Bring it in when you're ready.
Then the line "Vehicle 01 is the first step: a four-rotor aircraft that flies an order from the shop to your door." Reference: Wing's Fast / Convenient / Eco friendly; Zipline's Fresher / Worry-free / Less waiting.

### F. The first product (replaces the showcase)
One section, no carousel: h2 "The first product: Vehicle 01.", the side-view drawing, four spec rows (Rotors 4 · Capacity up to 15 lb · Flight time 45 minutes · Built for city and local deliveries; *facts from Tanner, 2026-11-05, also applied to Products*), "About Vehicle 01" to `/products#vehicle-01` and "See the app and Dispatch" to `/products`. The app and Dispatch keep their full sections on Products. This also retires S-01 to S-04 from the design review.

### G. Questions a neighbour would ask (new), at the bottom, collapsible
Sits last before the closing, so the doubts are answered right before the ask. Each question is a collapsible row (native `details`/`summary`, the first one open, a plus that turns to a minus), numbered like the Press manual.
- h2 "Questions a neighbour would ask."
- Intro: "Packet flies over streets people live on. These are the questions we would ask, and the answers as they stand."
- Seven Q&As, numbered like the Press manual (1.0 to 7.0), as an accordion:
  1. **Is it safe?** Vehicle 01 flies under the FAA's rules for small unmanned aircraft, on routes Dispatch plans in advance and follows from pickup to drop-off. [SAFETY DETAILS TO FOLLOW]
  2. **How loud is it?** [NOISE MEASUREMENT TO FOLLOW], measured at [DISTANCE]. We will publish it before the first flight.
  3. **Where does it land?** At the spot you chose in the app, with open sky above it. It sets the order down and leaves.
  4. **What if I'm not home?** It is left at your spot, like a package. The app shows you when it arrived.
  5. **What about rain and wind?** Flights pause in [CONDITIONS TBD]. The app says so before you order.
  6. **Does it record my street?** [PRIVACY STATEMENT TO FOLLOW]
  7. **Who is flying it?** Packet's own team in Seattle, with Dispatch watching every flight.
- Every bracket is a fact the team has to supply or decide. The section is worth building with the brackets showing: it tells a visitor the questions are taken seriously.

### H. Who is building Packet (new)
A founder's note of three or four sentences, signed [NAME], [TITLE], Seattle. Why this, why here, what the first year is for. No university, no class, no team name (spec anti-goals). The Press fact sheet already carries the leadership placeholders.

### I. What's next (new)
A timeline drawn as the dotted route motif with the red block at the current stop: **Sign-ups open** now · **First test flights** [DATE] · **First deliveries, with [SHOP]** [LAUNCH DATE] · **[NEIGHBOURHOOD]** [DATE]. Pre-launch pages that state a date convert better than ones that say "soon".

### J. Closing call to action and footer, one piece
The closing form, the tunnel and the footer share one framed block (*Tanner, 2026-11-05*): four corner marks at the block's corners, echoing the emblem, the tunnel's rings rushing toward their vanishing point behind the form, and the footer row (emblem, copyright, the shops line, the links) inside the same frame at the bottom. Keep the heading and form. Add the offer and the referral:
- "Sign up now and [OFFER: first delivery on us / founding-address status]."
- "Know a neighbour who would want this? Send them the link." (a `?ref=` parameter can follow later; attribution capture already stores sources)
- A slim strip above the footer for the other audience: "Run a shop near U Village? Write to [EMAIL]." (Manna's "Partner with Manna")

### K. Footer (keep, add contact)
Add [EMAIL].

## 4. Priorities

| Section | Value | Effort | Needs from the team |
|---|---|---|---|
| C. Where Packet flies first | High: the page becomes local and real | Medium: data exists, one drawing | Review the boundary; next neighbourhoods |
| B. What you can get | High: the first concrete thing on the page | Low: drawings exist | Shop names, prices |
| G. Questions a neighbour would ask | High: trust | Low: copy | Answers to 1, 2, 5, 6 |
| E. Why, as benefits | Medium | Low | Delivery time |
| I. What's next | Medium: a reason to sign up now | Low: one drawing | Dates, first shop |
| H. Founder's note | Medium: people | Low | Names, titles, the note |
| F. Vehicle 01, single section | Medium: simpler, honest | Low | none |
| A. Proof strip, J. offer and referral | Medium | Low | Launch date, the offer |
| D. Fourth step | Low to medium | Low | Landing-spot rule |
| J. For shops strip, K. email | Low | Low | Contact email |

Suggested order of work: B and C first (they change what the page is), then G, then E and I, then F, H and the rest. Each section is a spec §6 addition before it is built, per the "copy exactly as the spec writes it" rule.

## 5. Scroll-locked sections

Three blocks pin to the viewport while the visitor scrolls through them, and the scroll drives what happens on the stage. The rule for choosing them: the scroll has to perform the point of the section, not just hold a picture still.

| Block | What the scroll does | Why there |
|---|---|---|
| C. Where Packet flies first | The boundary draws itself around the university area, the hub's marks close in on U Village, then the neighbourhoods name themselves one at a time: University Village, the U District, the north campus, Bryant, Mercer Court. The "next" line and "Check your street" arrive last. | A neighbour watches their own street get named. The section is about place, so the scroll adds places. |
| E. Why (the delivery) | The package lifts off at the shop, crosses above the street and sets down at the door, with each benefit arriving at its moment: "Minutes, not an hour" at lift-off, "Nothing on your street" over the street, "Set down, not handed off" at the door. | The scroll performs the delivery. Each benefit is tied to the instant that proves it. This is the premise, so it gets the longest lock. |
| J. Closing | The crop-mark tunnel rushes toward the visitor as the form comes in. | Momentum into the one action, using the brand's own motion motif. |

Not locked, on purpose: the hero (the address check has to be reachable at once; it keeps its load-time intro instead), How it works (the mechanics of the app, kept short and scannable; its route still draws in on scroll as built), the questions (read, not watched), the timeline and the team note.

Technique, in the mockup and for the build: a tall section (2 to 3 screens) with a `position: sticky` stage, and CSS scroll-driven animations (`view-timeline-name` on the section, `animation-timeline` and `animation-range: contain …` on the moving parts) so no JavaScript is needed. The package follows the route with `offset-path`. Browsers without scroll-driven animations get the section at its normal height showing the end state; reduced motion shows the end state too. The map's boundary and hub move out of the map image into an inline layer so they can draw.

## 6. What stays within the rules

Four inks, drawings not photos, one station-sign button and one mustard tag per screen, the leading lines once, no startup-marketing words, no invented specs, no university or class, the aircraft only as a technical drawing. The new sections add three drawings in the house style (items row, first-area map, timeline route) and reuse the existing ones.

## Sources

- Wing, Zipline and Manna homepages, fetched 2026-11-04: https://wing.com/ · https://www.zipline.com/ · https://www.manna.aero/
- Landing-page anatomy: https://diversekit.com/blog/landing-page-design-best-practices · https://arceniktechnologies.com/blogs/landing-page-design-best-practices-2026 · https://skymooninfotech.com/blogs/landing-page-best-practices/ · https://landingi.com/blog/components-of-an-effective-landing-page/
- Pre-launch and waitlist pages: https://getlaunchlist.com/blog/waitlist-landing-page-examples-that-convert · https://unicornplatform.com/blog/waitlist-landing-page/ · https://prefinery.com/blog/building-a-waitlist-for-your-startup-the-complete-step-by-step-guide
- Section references on Mobbin: Zipline "How it works" and "How we deliver" map, Mercury and Zendesk FAQ sections.
