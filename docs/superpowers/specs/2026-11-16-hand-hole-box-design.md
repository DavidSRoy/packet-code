# Hand-hole cardboard box

Date: 2026-11-16. Status: approved in conversation, not yet built or tested.

## Why

The first cardboard box copied the printed BX-005: the jaws hooked under a ledge on the outside of each end wall. That box took 22 folds, 8 pieces of tape and 2 glue lines, and the ledge alone caused 12 of the folds. That is too much for the person who packs the food. The grab mechanism is not final, so the box and the grab can change together.

## Goals

- The person packing can close the box in a few moves, with no tools.
- A standard box plant can make it: one piece, a common style.
- The lid stays flat and at the same height, so the lid tags and the landing do not change.

Not goals: keeping the current jaw tips, or matching the printed box's inside size.

## Approaches

| | Box | Drone change | Tradeoff |
|---|---|---|---|
| A. Hand holes (chosen) | One-piece carton with a hole in each end wall | New jaw tips: a tongue about 20 mm lower than the hook | Needs about 13 mm clear inside each end; the holes leak some heat |
| B. Forks from below | Any plain box | Long L-shaped jaws that slide under the floor | Every pickup point needs a raised stand |
| C. Top handle and one latch | Gable-top carton with a handle | One latch pin | No flat lid, so the tags and the landing vision must be redone |

A was chosen because it keeps the flat lid and needs nothing at the pickup point.

## The box

- One piece: four walls in a row, a lid hinged on one long wall with a tuck flap, a dust flap on each end wall, four bottom flaps.
- Outside 246 x 202 mm, lid top 154.4 mm above the ground. Inside about 238 x 194 x 142 mm with 4 mm board.
- The length puts the end walls where the tips of the printed ledges were. The width leaves 3.9 mm to each landing leg.
- Hand hole: 90 x 30 mm, centred on each end wall, top edge 25 mm below the lid top. Three sides are cut and the top is a crease, so the flap stays shut until a jaw pushes it in.
- Factory version: a self-locking (crash-lock) bottom and a glued side seam, so it ships flat and pops open. The hand-cut prototype tapes the bottom flaps and the tab instead. Everything above the floor is the same.

## The grab

1. The drone lands over the box with the jaws open. The landing legs centre the box, as now.
2. The jaws close. Each tongue pushes a flap in and enters the hole by about 13 mm.
3. The box hangs from the top edge of the two holes. The folded flap doubles the board there.
4. After landing, the jaws open and the tongues slide out.

The hole is sized for a tongue up to 60 mm wide and 6 mm thick. That leaves about 15 mm of room sideways and 12 mm in height.

## Not known yet

- How much load the hole edge takes. No test has been done. Hang 5 kg from a test box before flying one.
- The jaw travel and tip shape. Only the jaw bounding boxes are in the repo.
- Whether the lid stays shut in the downwash without tape.
- How much heat the holes lose.

## Files

`backend/tools/box/box_pattern.py` draws the pattern and the cutting guide. The blank fits one flat 24 x 36 in sheet. Its constants are the numbers above.
