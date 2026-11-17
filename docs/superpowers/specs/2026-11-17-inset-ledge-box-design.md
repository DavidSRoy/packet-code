# Inset-ledge cardboard box

Date: 2026-11-17. Status: drawn and checked on paper, not yet cut or tested. Replaces the hand-hole note of 2026-11-16.

## Why

The gripper stays as it is. Its two jaws close inward and each hooks under a ledge at one end of the box. A cardboard box has to give those hooks the same ledge, in the same place.

Two earlier boxes did not work out:

- The ledge copy (the first box) folded a ledge onto the outside of each end wall, like the printed BX-005. It took 22 folds, 8 pieces of tape and 2 glue lines. That is too much for the person who packs the food.
- The hand-hole box (2026-11-16) was simple to fold, but the jaws had to lift by the top edge of a hole about 20 mm lower than the ledge. That needs new jaw tips, so it does not work with the gripper the drone has.

## Goals

- The current gripper holds the box with no change to the jaws.
- The person packing can close the box in a few moves.
- One piece of board, a common carton style.
- The lid stays flat and at the same height, so the lid tags and the landing do not change.

Not a goal: matching the printed box's inside size.

## Approaches

| | Box | Drone change | Tradeoff |
|---|---|---|---|
| A. Inset ledge (chosen) | One-piece carton. The top of each end wall folds inward, with a slot under the fold | None | The lid must be taped, because it holds the ledge flaps down |
| B. Outside ledge | Ledge folded onto the outside of each end wall | None | 22 folds, and the ledge is glued |
| C. Hand holes | One-piece carton with a hole in each end wall | New jaw tips | Does not work with the current gripper |

A was chosen because it is the only one that keeps both the gripper and a simple fold.

## The box

- One piece: four walls in a row, a lid hinged on one long wall with a tuck flap, a ledge flap on top of each end wall, four bottom flaps. 12 folds, all the same way.
- Outside 246 x 202 mm. The end faces sit where the tips of the printed ledges are. The width leaves 3.9 mm to each landing leg.
- Ledge flap: the top 60 mm of each end wall folds inward and lies flat. Its underside is 146.9 mm above the ground, the height of the underside of the printed ledge.
- Jaw slot: 136 x 22 mm, cut out of each end wall just under the fold. The jaws sit within a 120 mm width, so the slot leaves 8 mm each side, and 31 mm of wall stays on each side of the slot.
- Lid: 224.6 mm long, 1 mm shorter than the printed BX-006 lid, so it leaves the ends of the ledge flaps uncovered as the printed lid does. With 4 mm board its top is at 154.9 mm, 0.5 mm above the printed lid top.
- The tuck flap is 116 mm wide so that it drops between the two ledge flaps.
- Inside about 238 x 194 x 139 mm with 4 mm board.

## The grab

1. The drone lands over the box with the jaws open, as now.
2. The jaws close. Each hook passes through a slot: 4 mm of wall, then about 9 mm into the box.
3. The hooks lift against the underside of the ledge flaps. The flaps push up on the lid, and the lid is held by its hinge on the back wall and the tape on the front wall.
4. After landing, the jaws open and the hooks slide out.

## Not known yet

- The real shape of the hooks. Only the jaw bounding boxes are in the repo, so the slot is sized from those.
- How much load the ledge flap and the taped lid take. Hang twice the payload from a test box before flying one.
- Whether a closure with no tape (a locking tab or a peel strip) holds the lid well enough. The prototype uses tape.
- How much heat the slots lose.

## Files

`backend/tools/box/box_pattern.py` draws the pattern, the cutting guide and a layout on a 20 x 20 x 34 in wardrobe box. The blank also fits one flat 24 x 36 in sheet. Its constants are the numbers above.
