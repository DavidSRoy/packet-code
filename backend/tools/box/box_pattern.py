#!/usr/bin/env python3
"""Cut pattern for the Packet cardboard box: one piece, held by the gripper the drone has now.

The gripper's two jaws close inward. The end of each jaw is a U on its side: an upper
prong, a gap and a lower prong. On the printed box a ledge that sticks out from the end
wall goes into the gap. Here the ledge is inset: the top of each end wall folds inward as
a flap, and a slot cut just under the fold lets the lower prong reach in under it. The rest is a plain carton: four walls in a row, a lid hinged on one
long wall with a tuck flap, and four bottom flaps.

  python3 box_pattern.py [board_thickness_mm] [out.svg] [tabloid|a3]

Writes the pattern, a cutting guide (.md), a layout drawing (.svg) and layout guide (.md) for a wardrobe box,
and a 1:1 print template for Arch D paper (.svg). With a paper name it also writes that template as
sheets for an office printer.
All sizes are mm and the pattern is 1:1. Creases are drawn at the board mid-plane, so a
panel between two creases is its outside size minus one board thickness.
"""
import sys

# From the printed BX-005 / BX-006 and the drone (backend/tools/sim/lid_camera_sim.py)
LEDGE_UNDER = 146.9  # underside of the ledge the lower prongs lift against, above the ground
LEDGE_TOP = 151.5    # top of the printed ledge
LID_TOP_CAD = 154.4  # printed lid top above the ground
LID_LEN = 225.6      # printed lid length: the ledge is left uncovered beyond it
# The jaws (Packet Pickup v2), measured closed on the printed box with the drone landed, above the ground
PRONG_REACH = 8.0    # the lower prong's tip, in from the end face of the box
PRONG_TOP = 143.0    # top of the lower prong: it rises to the ledge before the box lifts
PRONG_BOTTOM = 137.0 # underside of the lower prong, the lowest point of the jaw
UPPER_OVER_LID = 158.5     # underside of the upper prong where it reaches over the lid
UPPER_OVER_LEDGE = 156.5   # underside of the upper prong near its root, over the ledge
JAW_HALF_W = 60.0    # the jaws are 120 wide, centred
LEG_GAP = 209.8      # clear width between the landing legs at lid height
L_OUT = 246.0        # outside length: the end faces sit where the tips of the printed ledges are
TAG_AREA = (218.0, 190.0)    # the lid tags without the sticker's white margin (companion/stickers_218x200)

# The box
W_OUT = 202.0        # outside width

# Bench knobs: change these after the first test fit
SLACK = 0.5          # clearance per side where parts slide together
FIT = 3.0            # how far the cardboard lid top may sit from the printed one
LEG_MARGIN = 3.5     # least room to each landing leg
SLOT_MARGIN = 8.0    # jaw slot width past the jaws, each side
SLOT_H = 22.0        # jaw slot height below the ledge
LEDGE_FLAP = 60.0    # depth of the flap the lower prongs sit under
TAB = 25.0           # side seam tab
TAB_INSET = 8.0      # the tab stops this far short of the wall top and bottom
TUCK = 25.0          # tuck flap depth
TUCK_GAP = 3.0       # room between the tuck flap and each ledge flap
LINER = 5.0          # foil bubble liner inside the box (0.19 in roll); 0 leaves it out

# The board to cut from. A flat 24 x 36 in sheet takes the blank in one piece.
SHEET_W, SHEET_L = 609.6, 914.4
# Or a 20 x 20 x 34 in wardrobe box opened flat (nominal sizes, measure yours)
BOX_PANEL_W, BOX_PANEL_H, BOX_FLAP = 508.0, 864.0, 254.0   # panel width and height, flap depth
BOX_TRIM = 5.0       # stay this far inside the box's other creases
BOX_FOOT = 40.0      # gap left below the blank, above the bottom crease
PRINT_TOP = 12.0     # margin above the blank on the Arch D print template
PRINT_END = 5.0      # least margin kept at the end 2 side of that page
# The same template as sheets for an office printer: paper width, height and name, landscape
PAPERS = {"tabloid": (431.8, 279.4, "11 x 17 in (Tabloid)"), "a3": (420.0, 297.0, "A3")}
TILE_W, TILE_H = 350.0, 256.0    # the part of the drawing each sheet carries
TILE_X, TILE_Y = 330.0, 117.0    # where the first joins cross the blank: from its left end, and above the ground


def layout(t: float) -> dict[str, float]:
    """Crease and edge positions. x runs along the row of walls from the tab edge; y is height above the ground."""
    xa = TAB
    xb = xa + L_OUT - t
    xc = xb + W_OUT - t
    xd = xc + L_OUT - t
    lid_top = LEDGE_UNDER + 2 * t        # ledge flap, then the lid on top of it
    ya = lid_top - t / 2
    lid = W_OUT - 2 * t - SLACK
    lid_len = LID_LEN - 2 * SLACK
    lx0 = xa + (L_OUT - t - lid_len) / 2
    tuck_half = (L_OUT - t) / 2 - LEDGE_FLAP - TUCK_GAP   # the tuck flap drops between the two ledge flaps
    mid = xa + (L_OUT - t) / 2
    g = {
        "t": t,
        "xa": xa,                        # crease: tab to side A (back wall, carries the lid)
        "xb": xb,                        # crease: side A to end 1
        "xc": xc,                        # crease: end 1 to side B (front wall)
        "xd": xd,                        # crease: side B to end 2
        "xe": xd + W_OUT - t - 2 * SLACK,   # free edge of end 2
        "ys": t / 2,                     # side walls, bottom crease: their flaps are the outer floor layer
        "ye": 1.5 * t,                   # end walls, bottom crease: their flaps are the inner floor layer
        "fd": (W_OUT - t) / 2 - SLACK,   # bottom flap depth
        "lid_top": lid_top,
        "ya": ya,                        # side A, lid crease
        "yb": lid_top,                   # side B, top edge (flush with the lid top)
        "yd": LEDGE_UNDER + t / 2,       # end walls, ledge flap crease: the flap's underside is the ledge
        "lid": lid,                      # lid depth, hinge crease to tuck crease
        "yt": ya + lid,                  # tuck crease
        "lx0": lx0,                      # lid, left and right edges: shorter than side A, like the printed lid
        "lx1": lx0 + lid_len,
        "ov": t / 2 + SLACK,             # flap insets from the wall creases
        "tx0": mid - tuck_half,          # tuck flap, left and right edges
        "tx1": mid + tuck_half,
        "slot_w": 2 * (JAW_HALF_W + SLOT_MARGIN),
        "il": L_OUT - 2 * t,             # inside length
        "iw": W_OUT - 2 * t,             # inside width
        "ih": LEDGE_UNDER - 2 * t,       # inside height under the ledge flaps, over the end bottom flaps
    }
    check(g)
    return g


def check(g: dict[str, float]) -> None:
    """The folded box must fit the drone, put the ledge where the jaws expect it, and close on itself."""
    t = g["t"]
    near = lambda a, b: abs(a - b) < 1e-6
    assert W_OUT + 2 * LEG_MARGIN <= LEG_GAP, "the box fits between the landing legs"
    assert near(g["xb"] - g["xa"] + t, L_OUT) and near(g["xd"] - g["xc"] + t, L_OUT), "outside length"
    assert near(g["xc"] - g["xb"] + t, W_OUT), "outside width"
    assert near(g["ys"] - t / 2, 0), "the floor sits on the ground"
    assert near(g["ye"] - g["ys"], t), "the end bottom flaps lie flat on the side ones"
    assert 2 * g["fd"] < W_OUT - t, "the side bottom flaps do not overlap"
    assert near(g["yd"] - t / 2, LEDGE_UNDER), "the ledge flap's underside is at the printed ledge height"
    assert LEDGE_UNDER + t <= LEDGE_TOP + 1, "the ledge flap is no thicker than the printed ledge"
    assert abs(g["lid_top"] - LID_TOP_CAD) <= FIT, (
        f"{t} mm board puts the lid top at {g['lid_top']:.1f}, printed {LID_TOP_CAD}")
    assert near(g["ya"] + t / 2, g["lid_top"]) and near(g["yd"] + t / 2, g["lid_top"] - t), "the lid lies flat on the ledge flaps"
    assert near(g["lid"] + t / 2 + SLACK, W_OUT - 1.5 * t), "the tuck flap slides inside the front wall"
    assert g["tx1"] - g["tx0"] <= L_OUT - t - 2 * LEDGE_FLAP - 2 * SLACK, "the tuck flap drops between the ledge flaps"
    assert g["tx1"] - g["tx0"] >= 80, "the tuck flap is wide enough to hold"
    assert LEDGE_UNDER - PRONG_TOP >= 3, "the lower prong passes under the ledge flap as the jaws close"
    assert LEDGE_UNDER - SLOT_H <= PRONG_BOTTOM - 5, "the jaw slot is open below the lower prong"
    assert PRONG_REACH - t >= 3, "the lower prong reaches past the wall, under the ledge flap"
    assert g["lid_top"] + 1 <= UPPER_OVER_LID, "the upper prong clears the lid"
    assert LEDGE_UNDER + t + 2 <= UPPER_OVER_LEDGE, "the upper prong clears the ledge flap"
    assert (W_OUT - t - g["slot_w"]) / 2 >= 25, "wall beside the jaw slot"
    assert LEDGE_FLAP >= PRONG_REACH - t + 30, "the ledge flap reaches well past the lower prongs"
    assert (L_OUT - (g["lx1"] - g["lx0"])) / 2 >= PRONG_REACH - 3, "the lid leaves the ledge uncovered, as the printed lid does"
    assert TAG_AREA[0] <= g["lx1"] - g["lx0"] and TAG_AREA[1] <= g["lid"], "the lid tags fit the flat lid"
    assert min(g["il"], g["iw"], g["ih"]) - 2 * LINER > 50, "the liner leaves room for the food"
    assert g["xe"] <= SHEET_L and g["yt"] + TUCK - (g["ys"] - g["fd"]) <= SHEET_W, "the blank fits one 24 x 36 in sheet"


def slots(g: dict[str, float]) -> list[float]:
    """Left side of the jaw slot on end 1 and on end 2."""
    return [x + (W_OUT - g["t"] - g["slot_w"]) / 2 for x in (g["xb"], g["xd"])]


def body_outline(g: dict[str, float]) -> list[tuple[float, float]]:
    xa, xb, xc, xd, xe, lx0, lx1 = (g[k] for k in ("xa", "xb", "xc", "xd", "xe", "lx0", "lx1"))
    ys, ye, fd, ya, yb, yd, yt, ov, tx0, tx1 = (g[k] for k in ("ys", "ye", "fd", "ya", "yb", "yd", "yt", "ov", "tx0", "tx1"))
    top = yd + LEDGE_FLAP
    return [   # counter-clockwise from the bottom of the tab
        (0, ys + TAB_INSET), (xa, ys + TAB_INSET), (xa, ys),
        (xa + ov, ys), (xa + ov, ys - fd), (xb - ov, ys - fd), (xb - ov, ys), (xb, ys), (xb, ye),
        (xb + ov, ye), (xb + ov, ye - fd), (xc - ov, ye - fd), (xc - ov, ye), (xc, ye), (xc, ys),
        (xc + ov, ys), (xc + ov, ys - fd), (xd - ov, ys - fd), (xd - ov, ys), (xd, ys), (xd, ye),
        (xd + ov, ye), (xd + ov, ye - fd), (xe - ov, ye - fd), (xe - ov, ye), (xe, ye),
        (xe, yd), (xe - ov, yd), (xe - ov, top), (xd + ov, top), (xd + ov, yd), (xd, yd),
        (xd, yb), (xc, yb), (xc, yd), (xc - ov, yd), (xc - ov, top), (xb + ov, top), (xb + ov, yd), (xb, yd),
        (xb, ya), (lx1, ya), (lx1, yt), (tx1, yt), (tx1, yt + TUCK), (tx0, yt + TUCK), (tx0, yt),
        (lx0, yt), (lx0, ya), (xa, ya), (xa, ya - TAB_INSET), (0, ya - TAB_INSET),
    ]


def body_elements(g: dict[str, float], ox: float = 0.0, oy: float = 0.0) -> tuple[list[str], list[str]]:
    """The blank as SVG elements: cuts and creases. Its left end is at ox and the ground line (y = 0) at oy."""
    xa, xb, xc, xd, xe, lx0, lx1 = (g[k] for k in ("xa", "xb", "xc", "xd", "xe", "lx0", "lx1"))
    ys, ye, ya, yd, yt, ov = (g[k] for k in ("ys", "ye", "ya", "yd", "yt", "ov"))
    cut, fold = [], []
    P = lambda x, y: (ox + x, oy - y)

    def seg(out, x0, y0, x1, y1):
        (a, b), (c, d) = P(x0, y0), P(x1, y1)
        out.append(f'<line x1="{a:.2f}" y1="{b:.2f}" x2="{c:.2f}" y2="{d:.2f}"/>')

    cut.append('<polygon points="' + " ".join("{:.2f},{:.2f}".format(*P(x, y)) for x, y in body_outline(g)) + '"/>')
    for x0 in slots(g):                             # jaw slots: cut out, just under the ledge flap crease
        a, b = P(x0, LEDGE_UNDER)
        cut.append(f'<rect x="{a:.2f}" y="{b:.2f}" width="{g["slot_w"]:.2f}" height="{SLOT_H:.2f}"/>')
    seg(fold, xa, ys + TAB_INSET, xa, ya - TAB_INSET)
    for x in (xb, xc, xd):
        seg(fold, x, ye, x, yd)
    seg(fold, xa + ov, ys, xb - ov, ys)             # bottom flaps
    seg(fold, xb + ov, ye, xc - ov, ye)
    seg(fold, xc + ov, ys, xd - ov, ys)
    seg(fold, xd + ov, ye, xe - ov, ye)
    seg(fold, xb + ov, yd, xc - ov, yd)             # ledge flaps
    seg(fold, xd + ov, yd, xe - ov, yd)
    seg(fold, lx0, ya, lx1, ya)                     # lid hinge
    seg(fold, g["tx0"], yt, g["tx1"], yt)           # tuck flap
    return cut, fold


def liner_pieces(g: dict[str, float]) -> list[tuple[str, list[tuple[float, float]], int]]:
    """Foil bubble pieces: name, outline from the piece's bottom-left corner, and how many to cut."""
    w, d = g["il"] - 2 * SLACK, g["iw"] - 2 * SLACK
    h = g["ih"] - 2 * LINER                         # walls stand on the floor piece and carry the top piece
    ew = g["iw"] - 2 * LINER - 2 * SLACK
    gap = PRONG_REACH - g["t"] + 3                  # the top piece stops short of each end, clear of the lower prongs
    nw = g["slot_w"] + 10                           # notch that keeps the jaw slot clear
    nd = SLOT_H - LINER + 5
    n0 = (ew - nw) / 2
    box = lambda a, b: [(0, 0), (a, 0), (a, b), (0, b)]
    return [("FLOOR", box(w, d), 1), ("TOP", box(w - 2 * gap, d), 1), ("SIDE", box(w, h), 2),
            ("END", [(0, 0), (ew, 0), (ew, h), (n0 + nw, h), (n0 + nw, h - nd), (n0, h - nd), (n0, h), (0, h)], 2)]


def marks(g: dict[str, float]) -> tuple[list[tuple[float, str]], list[tuple[float, str]]]:
    """Mark-out distances for the blank: along the length from the left end, and up from the bottom edge."""
    xa, xb, xc, xd, xe, lx0, lx1 = (g[k] for k in ("xa", "xb", "xc", "xd", "xe", "lx0", "lx1"))
    ys, ye, fd, ya, yb, yd, yt, ov = (g[k] for k in ("ys", "ye", "fd", "ya", "yb", "yd", "yt", "ov"))
    s1, s2 = slots(g)
    along = sorted([
        (0, "left end: edge of the tab"),
        (xa, "crease 1: tab to side A"),
        (xa + ov, "side A bottom flap, left edge"),
        (lx0, "lid, left edge"),
        (g["tx0"], "tuck flap, left edge"),
        (g["tx1"], "tuck flap, right edge"),
        (lx1, "lid, right edge"),
        (xb - ov, "side A bottom flap, right edge"),
        (xb, "crease 2: side A to end 1"),
        (xb + ov, "end 1 flaps, left edge"),
        (s1, "end 1 jaw slot, left side"),
        (s1 + g["slot_w"], "end 1 jaw slot, right side"),
        (xc - ov, "end 1 flaps, right edge"),
        (xc, "crease 3: end 1 to side B"),
        (xc + ov, "side B bottom flap, left edge"),
        (xd - ov, "side B bottom flap, right edge"),
        (xd, "crease 4: side B to end 2"),
        (xd + ov, "end 2 flaps, left edge"),
        (s2, "end 2 jaw slot, left side"),
        (s2 + g["slot_w"], "end 2 jaw slot, right side"),
        (xe - ov, "end 2 flaps, right edge"),
        (xe, "right end: edge of end 2"),
    ])
    b0 = ys - fd
    up = sorted((y - b0, name) for y, name in [
        (b0, "bottom edge: side bottom flaps"),
        (ye - fd, "end bottom flaps, bottom edge"),
        (ys, "side walls, bottom crease"),
        (ye, "end walls, bottom crease"),
        (ys + TAB_INSET, "tab, bottom edge"),
        (LEDGE_UNDER - SLOT_H, "jaw slots, bottom edge"),
        (ya - TAB_INSET, "tab, top edge"),
        (LEDGE_UNDER, "jaw slots, top edge"),
        (yd, "end walls, ledge flap crease"),
        (ya, "side A, lid crease"),
        (yb, "side B, top edge"),
        (yd + LEDGE_FLAP, "ledge flaps, top edge"),
        (yt, "tuck flap crease"),
        (yt + TUCK, "top edge: tuck flap"),
    ])
    return along, up


def guide(g: dict[str, float], box: bool = False) -> str:
    """The cutting guide as Markdown, from the same numbers as the drawing. With box=True every distance is
    measured from a wardrobe box's corner crease and bottom edge instead of from the blank's own edges."""
    t = g["t"]
    along, up = marks(g)
    length, height = along[-1][0], up[-1][0]
    f = lambda v: f"{v:.1f}"
    if box:
        xc = g["xc"]
        side = lambda d: "0" if abs(d - xc) < 1e-6 else f"{abs(d - xc):.1f} {'left' if d < xc else 'right'}"
        rise = lambda d: f(d + BOX_FOOT)
    else:
        side = rise = f
    A = {name: side(d) for d, name in along}
    U = {name: rise(d) for d, name in up}
    low_edge = U["bottom edge: side bottom flaps"] if box else "the bottom edge"
    left_end = A["left end: edge of the tab"] if box else "the left end"
    top_edge = U["top edge: tuck flap"] if box else "the top edge"
    table = lambda rows, fmt: "\n".join(f"| {fmt(d)} | {name} |" for d, name in rows)
    size = lambda pts: f"{max(x for x, _ in pts):.1f} x {max(y for _, y in pts):.1f}"
    liner = ""
    if LINER:
        floor, top, side_piece, end = (pts for _, pts, _ in liner_pieces(g))
        liner = f"""
## Liner ({LINER:g} mm foil bubble)

Cut with scissors.

| Piece | Size | Number | Goes |
|---|---|---|---|
| Floor | {size(floor)} | 1 | On the floor |
| Side | {size(side_piece)} | 2 | Along each long wall, standing on the floor piece |
| End | {size(end)} | 2 | Between the side pieces at each end |
| Top | {size(top)} | 1 | Laid on top of the wall pieces, centred, after the food is in |

Cut a notch {end[3][0] - end[6][0]:.0f} wide and {end[3][1] - end[4][1]:.0f} deep in the middle of the top edge of each end piece. The notch and the short top piece keep the jaw slots clear.
"""
    if box:
        pw, ph = BOX_PANEL_W, BOX_PANEL_H
        head = f"""# Layout guide: the blank on a 20 x 20 x 34 in wardrobe box, {t:g} mm board

Written by `box_pattern.py` from the same numbers as the drawings. All sizes are mm.

Every distance here is measured from two lines the wardrobe box already has: the corner crease in the middle of the opened box, and its bottom edge. The drawing ending `_on_wardrobe_box.svg` shows where the blank sits.

## Prepare the wardrobe box

1. Measure the board thickness. This guide is for {t:g} mm board. If yours differs by more than 0.5 mm, run the script again with your thickness. The pattern does not work with board of 6 mm or more.
2. Find the corner where the box is glued together. Cut the box open down that corner.
3. Cut the top flaps and the bottom flaps off along their creases. That leaves a flat sheet of four panels with three creases, about {4 * pw:.0f} x {ph:.0f}.
4. Lay the sheet with the plain inside face up. Hand holes and bar notches are near one end: put that end away from you. The edge toward you is the bottom edge.
5. The middle crease is the corner crease. Crease 3 of the blank goes on it, and it already folds the right way.
6. Check the size. Each panel beside the corner crease must be at least {xc + BOX_TRIM:.0f} wide (the listing says {pw:.0f}) and {height + BOX_FOOT:.0f} tall (the listing says {ph:.0f}).
7. Check that no hand hole, notch or extra crease falls inside the blank, which reaches {f(height + BOX_FOOT)} up from the bottom edge. If one does, add the same amount to every "up" distance to move the blank clear. There is {ph - height - BOX_FOOT:.0f} to spare.

The flutes (the ribs inside the board) run away from you, up the walls of the blank. Every fold goes toward you.

## Mark out

The blank is {f(length)} x {f(height)}. It starts {A['left end: edge of the tab']} of the corner crease and ends {A['right end: edge of end 2']} of it. Its bottom edge is {BOX_FOOT:g} above the bottom edge of the sheet.
The four walls sit side by side in a row: the tab, side A (back) and end 1 are left of the corner crease, and side B (front) and end 2 are right of it.

Along, from the corner crease:

| mm | Line |
|---|---|
{table(along, side)}

Up, from the bottom edge of the sheet:

| mm | Line |
|---|---|
{table(up, rise)}
"""
        corner = "\n- Crease 3 is the corner crease the wardrobe box already has. Do not score it again."
    else:
        head = f"""# Cutting guide: cardboard box for the current gripper, {t:g} mm board

Written by `box_pattern.py` from the same numbers as the drawing. All sizes are mm.

The box is one piece. The top of each end wall folds inward as a ledge flap, and a slot just under the fold lets the lower prong of each gripper jaw reach in under it.

## Check the board first

- Thickness: this guide is for {t:g} mm board. If yours differs by more than 0.5 mm, run the script again with your thickness.
- Board: single-wall C-flute. The blank is {f(length)} x {f(height)}.
- From a 20 x 20 x 34 in wardrobe box: use the guide ending `_on_wardrobe_box_guide.md` instead of this one. It measures from the box's own creases.
- From a flat 24 x 36 in sheet ({SHEET_W:g} x {SHEET_L:g}): one blank fits with {SHEET_L - length:.0f} to spare in length, so start from a square end.
- Flutes (the ribs inside the board) run up the walls, across the {f(length)} length of the blank.
- Mark out on the plain inside face. That face ends up inside the box, and every fold goes toward you.

## Mark out

Draw a rectangle {f(length)} x {f(height)}. Take every measurement from its left end or its bottom edge.
The four walls sit side by side in a row: tab, side A (back), end 1, side B (front), end 2.

Along the length, from the left end:

| mm | Line |
|---|---|
{table(along, side)}

Up, from the bottom edge:

| mm | Line |
|---|---|
{table(up, rise)}
"""
        corner = ""
    return head + f"""
## Cut

1. Bottom flaps. Keep four flaps below the walls and cut away the rest:
   side A from {A['side A bottom flap, left edge']} to {A['side A bottom flap, right edge']} and side B from {A['side B bottom flap, left edge']} to {A['side B bottom flap, right edge']}, both from {low_edge} up to {U['side walls, bottom crease']};
   end 1 from {A['end 1 flaps, left edge']} to {A['end 1 flaps, right edge']} and end 2 from {A['end 2 flaps, left edge']} to {A['end 2 flaps, right edge']}, both from {U['end bottom flaps, bottom edge']} up to {U['end walls, bottom crease']}.
   That leaves a {f(2 * g['ov'])} wide slot at each of creases 2, 3 and 4.
2. Tab. Keep the strip from {left_end} to {A['crease 1: tab to side A']}, between {U['tab, bottom edge']} and {U['tab, top edge']} up. Cut away the corners above and below it.
3. Wall tops. Side A ends at {U['side A, lid crease']} up and side B at {U['side B, top edge']} up. The end walls end at {U['end walls, ledge flap crease']} up, outside their flaps.
4. Ledge flaps. Above each end wall keep a flap up to {U['ledge flaps, top edge']}: end 1 from {A['end 1 flaps, left edge']} to {A['end 1 flaps, right edge']}, end 2 from {A['end 2 flaps, left edge']} to {A['end 2 flaps, right edge']}.
5. Lid. Above side A keep the lid from {A['lid, left edge']} to {A['lid, right edge']}, up to {U['tuck flap crease']}, and the tuck flap from {A['tuck flap, left edge']} to {A['tuck flap, right edge']}, up to {top_edge}. The lid is shorter than side A on purpose, and the tuck flap is narrow so that it drops between the two ledge flaps.
6. Jaw slots. Cut a slot right out of each end wall: end 1 from {A['end 1 jaw slot, left side']} to {A['end 1 jaw slot, right side']}, end 2 from {A['end 2 jaw slot, left side']} to {A['end 2 jaw slot, right side']}, between {U['jaw slots, bottom edge']} and {U['jaw slots, top edge']} up. The top of the slot stops {f(t / 2)} below the ledge flap crease. Do not cut into the crease. Round the two top corners a little.

## Crease

Press a blunt edge along a ruler on this face. Do not cut through. Every fold goes toward you.

- Creases 1 to 4: up the walls at {A['crease 1: tab to side A']}, {A['crease 2: side A to end 1']}, {A['crease 3: end 1 to side B']} and {A['crease 4: side B to end 2']}.{corner}
- Bottom flaps: side A and side B at {U['side walls, bottom crease']} up, end 1 and end 2 at {U['end walls, bottom crease']} up.
- Ledge flaps: across each end wall at {U['end walls, ledge flap crease']} up, right across the top of the jaw slot.
- Lid: across side A at {U['side A, lid crease']} up.
- Tuck flap: at {U['tuck flap crease']} up.
{liner}
## Fold and fix

1. Fold the four walls into a tube. Glue or tape the tab inside the free edge of end 2.
2. Fold the two end bottom flaps in, then the two side bottom flaps over them. Tape along the seam.
3. Put the floor, side and end liner pieces in, if you use them.
4. Pack the food. Keep the top of each end wall clear for about {PRONG_REACH - t + 5:.0f} mm inside.
5. Fold the two ledge flaps in.
6. Close the lid onto the ledge flaps, tuck its flap inside the front wall and tape the whole front edge, corners included. The tape matters: the lid holds the ledge flaps down when the jaws lift.

The tags ({TAG_AREA[0]:g} x {TAG_AREA[1]:g}) fit on the lid, which is {f(g['lx1'] - g['lx0'])} x {f(g['lid'])}. A sticker bigger than the lid needs its white margin trimmed.

## How the gripper holds it

| | Printed box | This box |
|---|---|---|
| Ledge underside above the ground | {LEDGE_UNDER:g} | {LEDGE_UNDER:g} (underside of the ledge flap) |
| End face the jaws close on | {L_OUT:g} apart | {L_OUT:g} apart |
| Lower prong rises before the box lifts | {LEDGE_UNDER - PRONG_TOP:.1f} | {LEDGE_UNDER - PRONG_TOP:.1f} |
| Lower prong under the ledge | {PRONG_REACH:g} | {PRONG_REACH:g}: {t:g} of wall, then {PRONG_REACH - t:g} under the flap |
| Upper prong above the lid top | {UPPER_OVER_LID - LID_TOP_CAD:.1f} | {UPPER_OVER_LID - g['lid_top']:.1f} |
| Opening for the jaws, which are {2 * JAW_HALF_W:g} wide | 160 wide | {g['slot_w']:g} wide, {SLOT_H:g} tall |
| Lid top above the ground | {LID_TOP_CAD:g} | {g['lid_top']:.1f} |
| Lid length | {LID_LEN:g} | {f(g['lx1'] - g['lx0'])} |
"""


def ordinate(dims: list[str], notes: list[str], points: list[float], origin: float, at: float,
             vertical: bool = False, size: float = 16.0) -> None:
    """Distances from one datum line: a tick and a number at each point, along a line at `at`."""
    a, b = min(points + [origin]), max(points + [origin])
    ends = (at, a, at, b) if vertical else (a, at, b, at)
    dims.append('<line x1="{:.2f}" y1="{:.2f}" x2="{:.2f}" y2="{:.2f}"/>'.format(*ends))
    for p in points + [origin]:
        tick = (at - size / 2, p, at + size / 2, p) if vertical else (p, at - size / 2, p, at + size / 2)
        dims.append('<line x1="{:.2f}" y1="{:.2f}" x2="{:.2f}" y2="{:.2f}"/>'.format(*tick))
        label = f"{abs(p - origin):.1f}" if p != origin else "0"
        if vertical:
            where = f'x="{at - 0.8 * size:.2f}" y="{p + 0.35 * size:.2f}" text-anchor="end"'
        else:
            where = f'transform="translate({p + 0.35 * size:.2f} {at + 0.8 * size:.2f}) rotate(-90)" text-anchor="end"'
        notes.append(f'<text {where} font-size="{size}">{label}</text>')


def chain(dims: list[str], notes: list[str], points: list[float], at: float, names: list[str],
          vertical: bool = False, reach: float = 8.0, size: float = 5.0) -> None:
    """One dimension line through the given cut points: a tick at each point, a stub of
    length `reach` back toward the drawing, and the length of each run beside the line."""
    a, b = points[0], points[-1]
    ends = (at, a, at, b) if vertical else (a, at, b, at)
    dims.append('<line x1="{:.2f}" y1="{:.2f}" x2="{:.2f}" y2="{:.2f}"/>'.format(*ends))
    lo, hi = sorted((at - size / 2 - max(reach, 0), at + size / 2 - min(reach, 0)))
    for p in points:
        tick = (lo, p, hi, p) if vertical else (p, lo, p, hi)
        dims.append('<line x1="{:.2f}" y1="{:.2f}" x2="{:.2f}" y2="{:.2f}"/>'.format(*tick))
    for (p, q), name in zip(zip(points, points[1:]), names):
        label, mid = f"{name} {abs(q - p):.1f}".strip(), (p + q) / 2
        if vertical:
            where = f'transform="translate({at + 1.6 * size:.2f} {mid:.2f}) rotate(-90)" text-anchor="middle"'
        elif len(label) * size * 0.52 > abs(q - p):         # too long for its run: hang it below the line
            where = f'transform="translate({mid + 0.35 * size:.2f} {at + size:.2f}) rotate(-90)" text-anchor="end"'
        else:
            where = f'x="{mid:.2f}" y="{at - 0.6 * size:.2f}" text-anchor="middle"'
        notes.append(f'<text {where} font-size="{size}">{label}</text>')


def on_box(g: dict[str, float]) -> str:
    """The blank laid over a wardrobe box opened flat, drawn at 1:4. Crease 3 sits on one of the box's own
    corner creases, because the blank is longer than one panel."""
    xc, xe = g["xc"], g["xe"]
    low, high = g["ys"] - g["fd"], g["yt"] + TUCK
    pw, ph, fl = BOX_PANEL_W, BOX_PANEL_H, BOX_FLAP
    assert xc <= pw - BOX_TRIM and xe - xc <= pw - BOX_TRIM, "the blank fits the two panels either side of a corner crease"
    assert high - low + BOX_FOOT <= ph, "the blank fits the panel height"

    ox, oy = 150.0, 120.0
    top, bottom = oy + fl, oy + fl + ph                       # the creases above and below the panels
    corner = ox + 2 * pw                                      # the corner crease the blank folds on
    x0, ground = corner - xc, bottom - BOX_FOOT + low         # blank's left end; SVG y of the box's ground line
    canvas_w, canvas_h = ox + 4 * pw + 80, bottom + fl + 290
    box, dims, notes = [], [], []
    for i in range(4):
        x = ox + i * pw
        box.append(f'<rect x="{x:.1f}" y="{oy:.1f}" width="{pw:.1f}" height="{fl:.1f}" fill="#f1eee6" stroke-dasharray="14 10"/>'
                   f'<rect x="{x:.1f}" y="{bottom:.1f}" width="{pw:.1f}" height="{fl:.1f}" fill="#f1eee6" stroke-dasharray="14 10"/>'
                   f'<rect x="{x:.1f}" y="{top:.1f}" width="{pw:.1f}" height="{ph:.1f}" fill="white"/>')
    label = lambda x, y, s, size=22, anchor="middle": notes.append(
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}">{s}</text>')
    for i, s in enumerate(["PANEL 1: spare", "PANEL 2", "PANEL 3", "PANEL 4: spare"]):
        label(ox + (i + 0.5) * pw, top + 44, s)
    label(ox + 1.5 * pw, oy + fl / 2 + 8, "top flaps: cut off along the crease")
    label(ox + 0.5 * pw, bottom + fl - 30, "bottom flaps: cut off along the crease", 18)
    label(ox + 3.5 * pw, top + ph / 2, "&#8593; flutes run this way &#8595;")
    label(corner + 16, top + 110, "&#8592; put crease 3 on this corner crease", 22, "start")

    cut, fold = body_elements(g, x0, ground)
    fill = '<polygon points="' + " ".join(f"{x0 + x:.2f},{ground - y:.2f}" for x, y in body_outline(g)) + '"/>'
    big = dict(size=16.0, reach=0.0)
    chain(dims, notes, [ox + i * pw for i in range(5)], oy - 30, ["panel"] * 4, **big)
    chain(dims, notes, [oy, top, bottom, bottom + fl], ox - 40, ["flap", "panel", "flap"], vertical=True, **big)
    chain(dims, notes, [ox + pw, x0, corner, x0 + xe, ox + 3 * pw], bottom + 70,
          ["", "left of the corner", "right of the corner", ""], **big)
    chain(dims, notes, [top, ground - high, ground - low, bottom], ox + pw - 60, ["clear", "blank", "foot"],
          vertical=True, **big)
    # the main mark-out distances, from the two lines the wardrobe box already has
    ord_y, ord_x = bottom + 130, ox + pw - 150
    ordinate(dims, notes, [x0 + v for v in (0, g["xa"], g["xb"], g["xd"], xe)], corner, ord_y)
    label(x0 - 14, ord_y + 6, "from the corner crease:", 16, "end")
    heights = [low, g["ys"], g["yd"], g["yd"] + LEDGE_FLAP, g["yt"], high]
    ordinate(dims, notes, [ground - v for v in heights], bottom, ord_x, vertical=True)
    label(ord_x + 10, ground - high - 26, "up from the bottom edge:", 16, "end")
    for i, s in enumerate([
        f"Medium wardrobe box, 20 x 20 x 34 in, opened flat, inside face up. Drawn at 1:4, sizes in mm. Board {g['t']:g} mm.",
        "Panel sizes are the nominal ones from the listing. Measure your box before you cut.",
        "Cut the box open down its glued corner and cut the flaps off. The middle crease is the corner crease: "
        "crease 3 of the blank goes on it, and it already folds the right way.",
        "Measure along from the corner crease and up from the bottom edge. The guide ending "
        "_on_wardrobe_box_guide.md lists every line.",
        "Keep hand holes, bar notches and other creases out of the blank. If one is in the way, move the whole blank "
        f"up: there is {ph - (high - low) - BOX_FOOT:.0f} mm to spare.",
    ]):
        label(ox, bottom + fl + 70 + 34 * i, s, 22, "start")
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w / 4:.1f}mm" height="{canvas_h / 4:.1f}mm" viewBox="0 0 {canvas_w:.1f} {canvas_h:.1f}">
<rect width="100%" height="100%" fill="white"/>
<g id="box" stroke="#8d8878" stroke-width="2">{"".join(box)}</g>
<g fill="#ecd9b4" stroke="none">{fill}</g>
<g id="cut" fill="white" stroke="black" stroke-width="1.2">{"".join(cut[1:])}</g>
<g fill="none" stroke="black" stroke-width="1.2">{cut[0]}</g>
<g id="crease" fill="none" stroke="#1565c0" stroke-width="1.2" stroke-dasharray="10 6">{"".join(fold)}</g>
<g id="dims" fill="none" stroke="#444" stroke-width="0.9">{"".join(dims)}</g>
<g id="notes" font-family="Helvetica, Arial, sans-serif" fill="#333">{"".join(notes)}</g>
</svg>
'''


def _template(g: dict[str, float], tiled: bool = False) -> tuple[str, float, float]:
    """The blank alone at 1:1, laid out for an Arch D page (24 x 36 in), to print, lay on the board and cut
    through. It carries the two lines to put on a wardrobe box: the corner crease and the bottom edge.
    Returns the drawing as SVG groups, the blank's left end and the SVG y of the box's ground line.
    With tiled=True the notes fit one sheet of the tiled version and diamonds mark the joins."""
    t = g["t"]
    xa, xb, xc, xd, xe, lx0, lx1 = (g[k] for k in ("xa", "xb", "xc", "xd", "xe", "lx0", "lx1"))
    ys, ye, fd, ya, yb, yd, yt = (g[k] for k in ("ys", "ye", "fd", "ya", "yb", "yd", "yt"))
    low, high = ys - fd, yt + TUCK
    pw, ph = SHEET_L, SHEET_W                       # Arch D paper is the size of the flat board sheet
    right = max((pw - xe) / 2, PRINT_END)           # end 2 keeps a printable margin; the tab takes what is left
    ox, oy = pw - xe - right, PRINT_TOP + high      # blank's left end; SVG y of the box's ground line
    edge = oy - low + BOX_FOOT                      # SVG y of the wardrobe box's bottom edge
    assert ox >= 0 and edge + 20 <= ph, "the blank and its two guide lines fit an Arch D page"

    cut, fold = body_elements(g, ox, oy)
    X, Y = (lambda x: ox + x), (lambda y: oy - y)
    notes: list[str] = []
    marks_: list[str] = []
    guide_: list[str] = []

    def text(x, y, s, size=7.0, anchor="middle"):
        notes.append(f'<text x="{X(x):.2f}" y="{Y(y):.2f}" font-size="{size}" text-anchor="{anchor}">{s}</text>')

    def turned(x, y, s, size=5.0, anchor="middle"):
        notes.append(f'<text transform="translate({X(x):.2f} {Y(y):.2f}) rotate(-90)" font-size="{size}" '
                     f'text-anchor="{anchor}">{s}</text>')

    wall = (ye + yd) / 2
    for name, x0, x1 in [("SIDE A (back)", xa, xb), ("SIDE B (front)", xc, xd)]:
        text((x0 + x1) / 2, wall, name)
        text((x0 + x1) / 2, ys - fd / 2, "BOTTOM FLAP", 5)
    for name, x0 in [("END 1", xb), ("END 2", xd)]:
        mid = x0 + (W_OUT - t) / 2
        text(mid, wall - 10, name)
        text(mid, ye - fd / 2, "BOTTOM FLAP", 5)
        text(mid, yd + LEDGE_FLAP / 2 - 2, "LEDGE FLAP", 5)
        text(mid, LEDGE_UNDER - SLOT_H / 2 - 1.5, "JAW SLOT: cut out", 4.5)
    text((lx0 + lx1) / 2, ya + g["lid"] / 2, "LID")
    text((lx0 + lx1) / 2, ya + g["lid"] / 2 - 10, "the tags go on the other face", 5)
    text((g["tx0"] + g["tx1"]) / 2, yt + TUCK / 2 - 2, "TUCK FLAP", 5)
    turned(xa / 2 + 1.6, (ys + ya) / 2, "TAB")
    for n, x in enumerate((xa, xb, xc, xd), 1):
        turned(x + 6, ye + 10, f"crease {n}" + (": the corner crease, already there" if n == 3 else ""), 4.5, "start")

    # the two lines to lay on a wardrobe box: its corner crease (crease 3) and its bottom edge
    cx = X(xc)
    guide_.append(f'<line x1="{cx:.2f}" y1="0" x2="{cx:.2f}" y2="{Y(yb):.2f}"/>'
                  f'<line x1="{cx:.2f}" y1="{Y(ys):.2f}" x2="{cx:.2f}" y2="{ph:.2f}"/>'
                  f'<line x1="0" y1="{edge:.2f}" x2="{pw:.2f}" y2="{edge:.2f}"/>')
    notes.append(f'<text transform="translate({cx + 7:.2f} {Y(yb) - 34:.2f}) rotate(-90)" font-size="5" fill="#ad1457">'
                 "CORNER CREASE of the wardrobe box: lay this line on it</text>")
    notes.append(f'<text x="{ox + 8:.2f}" y="{edge - 3 if tiled else edge + 8:.2f}" font-size="5" fill="#ad1457">BOTTOM EDGE of the opened wardrobe box: '
                 f"lay this line on it. The blank starts {BOX_FOOT:g} mm above it.</text>")

    if tiled:
        # diamonds across the joins between sheets: each sheet prints half of every one on its edges
        join = oy - TILE_Y
        spots = [(X(TILE_X + c * TILE_W), join + d, True) for c in range(tile_columns(g) - 1) for d in (-206, -66, 64, 184)]
        spots += [(X(min(TILE_X + (c - 0.5) * TILE_W, xe - 40)), join, False) for c in range(tile_columns(g))]
        for (x, y, upright), name in zip(spots, "ABCDEFGHJKLMNPQR"):
            marks_.append(f'<polygon fill="#444" points="{x - 4:.2f},{y:.2f} {x:.2f},{y - 4:.2f} {x + 4:.2f},{y:.2f} {x:.2f},{y + 4:.2f}"/>')
            for s in (-1, 1):
                dx, dy = (s * 9, 1.5) if upright else (9, s * 4 + 1.5)
                notes.append(f'<text x="{x + dx:.2f}" y="{y + dy:.2f}" font-size="4" text-anchor="middle">{name}</text>')
        size, step, lines = 4.5, 7.5, [
            f"Packet cardboard box: print template, 1:1, for {t:g} mm board.",
            "This face is the inside of the box.",
            "Join the sheets first. Where a sheet says CUT, cut along that frame line,",
            "lay the cut edge on the frame line of its neighbour so that the",
            "diamonds meet, and tape the two sheets together.",
            f"Then check: crease 1 to crease 2 is {xb - xa:.1f} mm, and crease 2 to crease 4 is {xd - xb:.1f} mm.",
            "Lay the board with its inside face up and the flutes running up the walls.",
            "On a wardrobe box opened flat: put the CORNER CREASE line on the middle",
            "crease and the BOTTOM EDGE line on the bottom edge. Tape the template down.",
            "Solid black: cut. Dashed blue: crease. Press the creases through the paper",
            "with a blunt point, then cut the solid lines through it.",
            f"Cut the jaw slots right out. Their top edge stops {t / 2:g} mm below the ledge",
            "flap crease: do not cut into the crease.",
        ]
    else:
        # scale bars, to check that the print is not scaled
        bx, by = cx + 22, Y(yb) - 26
        marks_.append(f'<line x1="{bx:.2f}" y1="{by:.2f}" x2="{bx + 200:.2f}" y2="{by:.2f}"/>')
        marks_ += [f'<line x1="{bx + d:.2f}" y1="{by - 3:.2f}" x2="{bx + d:.2f}" y2="{by + 3:.2f}"/>' for d in range(0, 201, 50)]
        vx, vy = bx + 212, by - 100
        marks_.append(f'<line x1="{vx:.2f}" y1="{vy:.2f}" x2="{vx:.2f}" y2="{vy + 100:.2f}"/>')
        marks_ += [f'<line x1="{vx - 3:.2f}" y1="{vy + d:.2f}" x2="{vx + 3:.2f}" y2="{vy + d:.2f}"/>' for d in range(0, 101, 50)]
        notes.append(f'<text x="{bx + 100:.2f}" y="{by - 6:.2f}" font-size="5" text-anchor="middle">this bar is 200 mm long</text>')
        notes.append(f'<text transform="translate({vx - 6:.2f} {vy + 50:.2f}) rotate(-90)" font-size="5" text-anchor="middle">'
                     "this bar is 100 mm long</text>")
        size, step, lines = 5, 8.5, [
            f"Packet cardboard box: print template, 1:1, for {t:g} mm board. This face is the inside of the box.",
            "Print on Arch D (24 x 36 in) at 100 %, not fit to page. Then measure the two bars below with a ruler.",
            "Lay the board with its inside face up and the flutes running up the walls. Tape this sheet down on it.",
            "On a wardrobe box opened flat: put the CORNER CREASE line on the middle crease and the BOTTOM EDGE line on the bottom edge.",
            "Solid black: cut. Dashed blue: crease. Press the creases through the paper with a blunt point, then cut the solid lines through it.",
            f"Cut the jaw slots right out. Their top edge stops {t / 2:g} mm below the ledge flap crease: do not cut into the crease.",
            f"The tab ends {ox:.1f} mm from the left end of the paper and END 2 ends {right:.1f} mm from the right end. If the plotter",
            f"cannot print that close, feed the TAB end last: then only the tab's outer edge is lost, and you can rule it {TAB:g} mm from crease 1.",
        ]
    for i, s in enumerate(lines):
        notes.append(f'<text x="{cx + 12:.2f}" y="{PRINT_TOP + 8 + step * i:.2f}" font-size="{size}">{s}</text>')

    return f'''<g id="lay-on" fill="none" stroke="#ad1457" stroke-width="0.35">{"".join(guide_)}</g>
<g id="cut" fill="none" stroke="black" stroke-width="0.5">{"".join(cut)}</g>
<g id="crease" fill="none" stroke="#1565c0" stroke-width="0.5" stroke-dasharray="5 3">{"".join(fold)}</g>
<g id="scale" fill="none" stroke="black" stroke-width="0.35">{"".join(marks_)}</g>
<g id="notes" font-family="Helvetica, Arial, sans-serif" fill="#333">{"".join(notes)}</g>''', ox, oy


def template(g: dict[str, float]) -> str:
    """The print template as one Arch D page (24 x 36 in)."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_L}mm" height="{SHEET_W}mm" viewBox="0 0 {SHEET_L} {SHEET_W}">
<rect width="100%" height="100%" fill="white"/>
{_template(g)[0]}
</svg>
'''


def tile_columns(g: dict[str, float]) -> int:
    """How many sheets wide the tiled template is. The first column starts TILE_W left of the first join."""
    assert TILE_X <= TILE_W, "the first column of sheets covers the tab"
    return int(-(-(g["xe"] - TILE_X) // TILE_W)) + 1


def tiles(g: dict[str, float], paper: str = "tabloid") -> list[tuple[str, str]]:
    """The print template cut into landscape sheets for an office printer. Each sheet carries one
    TILE_W x TILE_H frame of the drawing, and the frames butt together. Returns (name, SVG) per sheet."""
    pw, ph, label = PAPERS[paper]
    mx, my = (pw - TILE_W) / 2, (ph - TILE_H) / 2
    assert min(mx, my) >= 8, "the paper leaves a margin around the frame"
    inner, ox, oy = _template(g, tiled=True)
    low, high = g["ys"] - g["fd"], g["yt"] + TUCK
    assert TILE_Y + TILE_H >= high + 1 and TILE_Y - TILE_H <= low - BOX_FOOT - 1, (
        "two rows of sheets cover the blank and the bottom edge line")
    cols, pages = tile_columns(g), []
    for r in range(2):
        for c in range(cols):
            tx, ty = ox + TILE_X + (c - 1) * TILE_W, oy - TILE_Y - (TILE_H if r == 0 else 0)
            bx, by = mx - 14, my + 30                       # a 100 mm bar in the left margin
            extra = [
                f'<rect x="{mx:.2f}" y="{my:.2f}" width="{TILE_W}" height="{TILE_H}" fill="none" stroke="#777" stroke-width="0.3"/>',
                f'<path d="M{bx:.2f} {by:.2f}v100M{bx - 2.5:.2f} {by:.2f}h5M{bx - 2.5:.2f} {by + 100:.2f}h5" fill="none" '
                'stroke="black" stroke-width="0.35"/>',
                f'<text transform="translate({bx - 3:.2f} {by + 50:.2f}) rotate(-90)" font-size="3.8" text-anchor="middle">'
                "this bar is 100 mm long</text>",
                f'<text x="{mx:.2f}" y="{my + TILE_H + 6:.2f}" font-size="3.8">Packet box template for {g["t"]:g} mm board. '
                f"Sheet {r * cols + c + 1} of {2 * cols}: row {r + 1}, column {c + 1}. Print at 100 % on {label}, landscape, "
                "then measure the bar at the left.</text>",
            ]
            for rr in range(2):                             # a small map of where this sheet goes
                for cc in range(cols):
                    extra.append(f'<rect x="{mx - 30 + 8 * cc:.2f}" y="{my + 4 + 7 * rr:.2f}" width="7" height="6" stroke="#444" '
                                 f'stroke-width="0.3" fill="{"#444" if (rr, cc) == (r, c) else "none"}"/>')
            if c:
                extra.append(f'<text transform="translate({mx - 2.5:.2f} {my + TILE_H / 2:.2f}) rotate(-90)" font-size="3.8" '
                             'text-anchor="middle">CUT along this line, then lay the cut edge on the right frame line of the '
                             "sheet to the left</text>")
            if r:
                extra.append(f'<text x="{mx + TILE_W / 2:.2f}" y="{my - 2.5:.2f}" font-size="3.8" text-anchor="middle">'
                             "CUT along this line, then lay the cut edge on the bottom frame line of the sheet above</text>")
            pages.append((f"r{r + 1}c{c + 1}", f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{pw}mm" height="{ph}mm" viewBox="0 0 {pw} {ph}">
<rect width="100%" height="100%" fill="white"/>
<clipPath id="frame"><rect x="{mx:.2f}" y="{my:.2f}" width="{TILE_W}" height="{TILE_H}"/></clipPath>
<g clip-path="url(#frame)"><g transform="translate({mx - tx:.2f} {my - ty:.2f})">
{inner}
</g></g>
<g font-family="Helvetica, Arial, sans-serif" fill="#333">{"".join(extra)}</g>
</svg>
'''))
    return pages


def svg(g: dict[str, float]) -> str:
    t = g["t"]
    xa, xb, xc, xd, xe, lx0, lx1 = (g[k] for k in ("xa", "xb", "xc", "xd", "xe", "lx0", "lx1"))
    ys, ye, fd, ya, yb, yd, yt = (g[k] for k in ("ys", "ye", "fd", "ya", "yb", "yd", "yt"))
    low, high = ys - fd, yt + TUCK
    outline = body_outline(g)
    assert min(y for _, y in outline) == low and max(y for _, y in outline) == high
    assert min(x for x, _ in outline) == 0 and max(x for x, _ in outline) == xe

    ox, top = 60.0, 40.0
    oy = top + high                                 # SVG y of the box's ground line
    bottom = oy - low
    pieces = liner_pieces(g) if LINER else []
    kx = ox + xe + 60                               # left edge of the liner columns
    col = max((x for _, pts, _ in pieces for x, _ in pts), default=0)
    width = (kx + 2 * col + 20 if pieces else ox + xe + 30) + 30
    height = bottom + 150

    cut, fold = body_elements(g, ox, oy)
    notes: list[str] = []
    dims: list[str] = []
    X, Y = (lambda x: ox + x), (lambda y: oy - y)

    def text(x, y, s, size=6.0):
        notes.append(f'<text x="{X(x):.2f}" y="{Y(y):.2f}" font-size="{size}" text-anchor="middle">{s}</text>')

    dim = lambda a, b: f"{a:.1f} x {b:.1f}"
    wall = (ye + yd) / 2
    for name, x0, x1, y0, y1 in [("SIDE A (back)", xa, xb, ys, ya), ("SIDE B (front)", xc, xd, ys, yb)]:
        text((x0 + x1) / 2, wall + 4, name)
        text((x0 + x1) / 2, wall - 6, dim(x1 - x0, y1 - y0))
        text((x0 + x1) / 2, ys - fd / 2, f"FLAP {fd:.1f}", 5)
    text((xa + xb) / 2, wall - 22, "&#8593; flutes run up the walls &#8595;", 5)
    for name, x0, x1, sx in [("END 1", xb, xc, slots(g)[0]), ("END 2", xd, xe, slots(g)[1])]:
        mid = x0 + (W_OUT - t) / 2
        text(mid, 62, name)
        text(mid, 52, dim(x1 - x0, yd - ye))
        text(mid, ye - fd / 2, f"FLAP {fd:.1f}", 5)
        text(mid, yd + LEDGE_FLAP / 2 - 2, f"LEDGE FLAP {LEDGE_FLAP:g}", 5)
        text(mid, yd + LEDGE_FLAP / 2 - 10, "the jaw's lower prong sits under this", 4.2)
        text(mid, LEDGE_UNDER - SLOT_H / 2 - 1.5, "JAW SLOT: cut out", 4.2)
        chain(dims, notes, [X(x0), X(sx), X(sx + g["slot_w"]), X(x0 + W_OUT - t)], Y(LEDGE_UNDER - SLOT_H - 12),
              ["", "slot", ""], reach=0, size=4.2)
    lid_mid = (lx0 + lx1) / 2
    text(lid_mid, ya + g["lid"] / 2 + 8, "LID")
    text(lid_mid, ya + g["lid"] / 2 - 2, dim(lx1 - lx0, g["lid"]))
    text(lid_mid, ya + g["lid"] / 2 - 14, "the tags go on the other face", 5)
    text(lid_mid, yt + TUCK / 2 - 2, f"TUCK FLAP {TUCK:g}", 5)
    notes.append(f'<text transform="translate({X(xa / 2) + 1.6:.2f} {Y((ys + ya) / 2):.2f}) rotate(-90)" '
                 f'font-size="5" text-anchor="middle">TAB {TAB:g}</text>')

    # dimension chains outside the drawing: the length of every panel between creases and cut edges
    chain(dims, notes, [X(v) for v in (0, xa, xb, xc, xd, xe)], bottom + 12,
          ["tab", "side A", "end 1", "side B", "end 2"])
    chain(dims, notes, [X(0), X(xe)], bottom + 30, ["overall"], reach=0)
    chain(dims, notes, [X(lx0), X(g["tx0"]), X(g["tx1"]), X(lx1)], top - 12, ["", "tuck", ""], reach=-8)
    chain(dims, notes, [X(lx0), X(lx1)], top - 28, ["lid"], reach=0)
    chain(dims, notes, [Y(v) for v in (high, yt, ya, ys, low)], ox - 14, ["tuck", "lid", "side A", "flap"],
          vertical=True, reach=-8)
    chain(dims, notes, [top, bottom], ox - 34, ["overall"], vertical=True, reach=0)
    chain(dims, notes, [Y(v) for v in (yd + LEDGE_FLAP, yd, ye, ye - fd)], X(xe) + 12, ["ledge flap", "end wall", "flap"],
          vertical=True)

    foil, ky = [], [top, top]
    for i, (name, pts, count) in enumerate(pieces):
        c = i // 2                                  # two pieces to a column
        px, py = kx + c * (col + 20), ky[c]
        w, h = max(x for x, _ in pts), max(y for _, y in pts)
        foil.append('<polygon points="' + " ".join(f"{px + x:.2f},{py + h - y:.2f}" for x, y in pts) + '"/>')
        notes.append(f'<text x="{px + w / 2:.2f}" y="{py + h / 2 + 12:.2f}" font-size="6" text-anchor="middle">LINER {name}, cut {count}</text>'
                     f'<text x="{px + w / 2:.2f}" y="{py + h / 2 + 22:.2f}" font-size="6" text-anchor="middle">{dim(w, h)}</text>')
        if len(pts) > 4:
            notes.append(f'<text x="{px + w / 2:.2f}" y="{py + (pts[3][1] - pts[4][1]) / 2 + 2:.2f}" font-size="4.5" '
                         f'text-anchor="middle">notch {pts[3][0] - pts[6][0]:.0f} x {pts[3][1] - pts[4][1]:.0f}</text>')
        ky[c] += h + 12

    lines = [
        f"Packet cardboard box for the current gripper, prototype 3. Board {t:g} mm. All sizes mm, drawn 1:1, "
        "creases at the board mid-plane. This face is the inside of the box.",
        "Solid black: cut. Dashed blue: crease. Every fold goes toward you.",
        f"Jaw slots: cut right out. The slot top stops {t / 2:g} mm below the ledge flap crease. Do not cut into the "
        "crease. The lower prong of each gripper jaw goes through the slot and sits under the folded ledge flap.",
        "Fold the walls into a tube and fix the tab inside END 2. Fold the END bottom flaps in first, then the SIDE "
        "flaps, and tape the seam.",
        "Fold the ledge flaps in, close the lid onto them, tuck its flap inside SIDE B and tape the whole front edge. "
        "The lid holds the ledge flaps down when the jaws lift.",
        f"Folded: {L_OUT:g} long, {W_OUT:g} wide, {g['lid_top']:.1f} to the lid top. Inside {g['il']:.1f} x {g['iw']:.1f} x "
        f"{g['ih']:.1f}. Blank {xe:.1f} x {high - low:.1f}.",
    ]
    if pieces:
        room = [g["il"] - 2 * LINER, g["iw"] - 2 * LINER, g["ih"] - 2 * LINER]
        lines.append(
            f"Green: foil bubble liner, {LINER:g} mm thick, a different material. The notch in the END pieces and the "
            f"short TOP piece keep the jaw slots clear. Room left for food: {room[0]:.0f} x {room[1]:.0f} x {room[2]:.0f}.")
    for i, s in enumerate(lines):
        notes.append(f'<text x="{ox}" y="{bottom + 54 + 12 * i:.2f}" font-size="6">{s}</text>')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}mm" height="{height:.0f}mm" viewBox="0 0 {width:.0f} {height:.0f}">
<rect width="100%" height="100%" fill="white"/>
<g id="cut" fill="none" stroke="black" stroke-width="0.4">{"".join(cut)}</g>
<g id="crease" fill="none" stroke="#1565c0" stroke-width="0.4" stroke-dasharray="4 2">{"".join(fold)}</g>
<g id="liner" fill="none" stroke="#2e7d32" stroke-width="0.4">{"".join(foil)}</g>
<g id="dims" fill="none" stroke="#444" stroke-width="0.25">{"".join(dims)}</g>
<g id="notes" font-family="Helvetica, Arial, sans-serif" fill="#333">{"".join(notes)}</g>
</svg>
'''


if __name__ == "__main__":
    thickness = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    out = sys.argv[2] if len(sys.argv) > 2 else f"packet_box_cardboard_t{thickness:g}.svg"
    geometry = layout(thickness)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg(geometry))
    stem = out.rsplit(".", 1)[0]
    with open(stem + "_guide.md", "w", encoding="utf-8") as fh:
        fh.write(guide(geometry))
    with open(stem + "_on_wardrobe_box.svg", "w", encoding="utf-8") as fh:
        fh.write(on_box(geometry))
    with open(stem + "_on_wardrobe_box_guide.md", "w", encoding="utf-8") as fh:
        fh.write(guide(geometry, box=True))
    with open(stem + "_arch_d.svg", "w", encoding="utf-8") as fh:
        fh.write(template(geometry))
    if len(sys.argv) > 3:                           # the template as sheets: tabloid or a3
        for name, page in tiles(geometry, sys.argv[3]):
            with open(f"{stem}_{sys.argv[3]}_{name}.svg", "w", encoding="utf-8") as fh:
                fh.write(page)
    for key, value in geometry.items():
        print(f"{key:8s} {value:8.2f}")
    print("wrote", out)
