# Pinned sections

Agreed with Tanner on 2026-11-04. Amends the landing spec (`2026-10-26-packet-landing-design.md` §6.3 and §6.5).

## Intent

Sections that show off how Packet works should hold the screen while the reader scrolls, so the animation plays out before the page moves on, the way Apple's product pages do. Each section gets its own time.

This is a pattern, not a one-off. How it works and the product showcase use it first. Any later section that animates (from the content work running in parallel) uses the same building block, so every pinned section feels the same.

## Goals

- How it works and the showcase pin while their animation plays, driven by scroll.
- One component and one hook own pinning. A section opts in by wrapping its content.
- Every pinned section behaves the same: same entry, same exit, same fallback.

## Non-goals

- Pinning the hero, Mission or the closing section now. They can opt in later.
- Snap points or scroll-speed changes.

## Anti-goals

- Blocking or hijacking the scroll wheel. Scrolling stays native: trackpad momentum, the keyboard (Space, Page Down, arrows), screen readers, find-in-page and anchor links like `#updates` keep working.
- A pinned section that hides content the reader can't reach.

## How it works (the mechanism)

`PinnedSection` renders a tall outer `<section>` and a `position: sticky; top: 0; height: 100svh` stage inside it. The outer height is `100svh × (1 + length)`, where `length` is the number of extra screen heights the section holds for. While the outer section passes, the stage stays put and `progress` runs 0 to 1:

```
progress = clamp01(-outerTop / (outerHeight - viewportHeight))
```

The section gets `{ progress, isPinned, scrollToProgress }` through a render prop. `scrollToProgress(p)` scrolls the window so the section sits at `p` (used by controls such as the showcase tabs).

Pinning is on only when both hold: `prefers-reduced-motion: no-preference` and `min-height: 600px`. Otherwise the section renders in normal flow with `progress = 1` (its finished state), so short landscape phones and reduced-motion readers get a plain page.

The pinned layout is CSS (`.pin` / `.pin-stage` in `globals.css`, height from `--pin-length`), so page height is right in the server render and anchor links land correctly before hydration. `usePinProgress` reads the same media query (`PIN_QUERY`) for progress; the two must stay identical.

`svh` keeps the stage from jumping as mobile browser bars show and hide.

`usePinProgress` replaces `useScrollProgress` (How it works was its only user), so there is one scroll reader.

## Rules for a pinned section

1. Its content must fit in one stage: `100svh` at 600px tall and up, down to 320px wide. Size art with `svh`-aware limits, not fixed pixel heights (the showcase caps its drawing at `min(380px, 38svh)`, and at `min(220px, 26svh)` on phones).
2. `length` is one screen height per beat of the story. Leave the last ~15% of progress as a hold on the finished state, so the reader sees it before the section scrolls away.
3. Map progress to the animation in the section, not in `PinnedSection`.
4. Interactive controls move the reader by scrolling (`scrollToProgress`), so scroll position and what's shown never disagree.
5. Reduced motion and short screens get the finished, unpinned layout. Every pinned section must look complete at `progress = 1`.

## The two sections

**How it works** (`length` 2). The trip drawing plays over the first 85% of progress and holds. The bullets fill as before.

**Showcase** (`length` = products, one screen height per product). Product `i` shows while progress is in slice `i`. The active tab fills with progress through its slice.
- The 7s auto-advance and the pause/play button are removed: scroll replaces the timer, and nothing moves on its own anymore.
- The tabs, the Next arrow and a 48px horizontal swipe scroll to that product's slice when pinned, and switch the product directly when unpinned.
- Unpinned (reduced motion, short screens): no timer, products change only through the controls, the active tab is full.

## Left to the builder

Exact padding inside the stage, and how the stage centers its content.

## Tasks

1. `pinProgress` and `sliceAt` math in `src/lib/pin.ts` with unit tests.
2. `PinnedSection` and `usePinProgress`; delete `useScrollProgress`.
3. How it works on `PinnedSection`.
4. Showcase on `PinnedSection`; drop the timer, pause button and their CSS; tabs fill by progress.
5. Update spec §6.3, §6.5 and the §10 verification line; verify on the production build at 390, 768, 1280 and 1440, and with reduced motion.

## Amended 2026-11-05: the rebuilt landing page

The landing page rebuild (landing spec §6) put the pattern to work on four sections: How it works, Where Packet flies first, Delivery and the closing piece. The showcase is gone with its section. Three things were added to the building block for them:

- **`--p` on the section.** `PinnedSection` sets the progress as a custom property, so a section can be staged in CSS alone: a ramp `--t` runs 0 to 1 while `--p` crosses `[--a, --b]`, and `.rise` elements fade and lift with it. The CSS default is `--p: 1`, the end state. `ramp()` in `lib/pin.ts` is the same function for the rare thing CSS cannot do (the delivery's package along its route).
- **A stage that does not fit renders in flow.** `usePinProgress` measures the stage in its pinned layout on mount and on resize; when its content is taller than the viewport the section gets `.pin-flow` and renders in flow at the end state. That keeps the anti-goal above (nothing the reader cannot reach) on short phones with long sections. The media query still owns the pre-hydration layout.
- **`className` and `stageClassName`** on `PinnedSection`, for a section's own styling hooks (the closing piece's frame).
