#!/usr/bin/env python3
"""Cut pattern for the Packet cardboard box: one piece, lifted by a hand hole in each end.

The box is a plain carton: four walls in a row, a lid hinged on one long wall with a
tuck flap, a dust flap on each end wall and four bottom flaps. The drone's two jaws
each slide a tongue into a hand hole near the top of an end wall and lift the box by
the top edge of the two holes.

  python3 box_pattern.py [board_thickness_mm] [out.svg]

Writes the pattern, a cutting guide (.md) and a layout on a wardrobe box (.svg).
All sizes are mm and the pattern is 1:1. Creases are drawn at the board mid-plane, so a
panel between two creases is its outside size minus one board thickness.
"""
import sys

# From the drone (backend/tools/sim/lid_camera_sim.py) and the printed BX-005 / BX-006
LID_TOP = 154.4      # lid top above the ground at the grab
LEG_GAP = 209.8      # clear width between the landing legs at lid height
L_OUT = 246.0        # outside length: the end walls sit where the printed ledge tips were
TAG_AREA = (218.0, 190.0)    # the lid tags without the sticker's white margin (companion/stickers_218x200)

# The box and the grab
W_OUT = 202.0        # outside width
HOLE_W, HOLE_H = 90.0, 30.0  # hand hole
HOLE_DROP = 25.0     # hole top edge below the lid top
TONGUE_W, TONGUE_T, TONGUE_REACH = 60.0, 6.0, 13.0   # the jaw tongue the hole is sized for; reach is past the wall face

# Bench knobs: change these after the first test fit
SLACK = 0.5          # clearance per side where parts slide together
LEG_MARGIN = 3.5     # least room to each landing leg
TAB = 25.0           # side seam tab
TAB_INSET = 8.0      # the tab stops this far short of the wall top and bottom
DUST = 60.0          # dust flap depth
TUCK = 25.0          # tuck flap depth
LINER = 5.0          # foil bubble liner inside the box (0.19 in roll); 0 leaves it out

# The board to cut from: a 20 x 20 x 34 in wardrobe box opened flat (nominal sizes, measure yours)
BOX_PANEL_W, BOX_PANEL_H, BOX_FLAP = 508.0, 864.0, 254.0   # panel width and height, flap depth
BOX_TRIM = 5.0       # stay this far inside the box's other creases
BOX_FOOT = 40.0      # gap left below the blank, above the bottom crease


def layout(t: float) -> dict[str, float]:
    """Crease and edge positions. x runs along the row of walls from the tab edge; y is height above the ground."""
    xa = TAB
    xb = xa + L_OUT - t
    xc = xb + W_OUT - t
    xd = xc + L_OUT - t
    ya = LID_TOP - t / 2
    lid = W_OUT - 2 * t - SLACK
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
        "ya": ya,                        # side A, lid crease
        "yb": LID_TOP,                   # side B, top edge (flush with the lid top)
        "yd": LID_TOP - 1.5 * t,         # end walls, dust flap crease
        "lid": lid,                      # lid depth, hinge crease to tuck crease
        "yt": ya + lid,                  # tuck crease
        "ov": t / 2 + SLACK,             # lid overhang past the wall creases; also the flap insets
        "ti": t / 2 + 2.0,               # tuck flap inset
        "hole_top": LID_TOP - HOLE_DROP,
        "il": L_OUT - 2 * t,             # inside length
        "iw": W_OUT - 2 * t,             # inside width
        "ih": LID_TOP - 3 * t,           # inside height, over the end bottom flaps
    }
    check(g)
    return g


def check(g: dict[str, float]) -> None:
    """The folded box must fit the drone and close on itself."""
    t = g["t"]
    near = lambda a, b: abs(a - b) < 1e-6
    assert W_OUT + 2 * LEG_MARGIN <= LEG_GAP, "the box fits between the landing legs"
    assert near(g["xb"] - g["xa"] + t, L_OUT) and near(g["xd"] - g["xc"] + t, L_OUT), "outside length"
    assert near(g["xc"] - g["xb"] + t, W_OUT), "outside width"
    assert near(g["ys"] - t / 2, 0), "the floor sits on the ground"
    assert near(g["ye"] - g["ys"], t), "the end bottom flaps lie flat on the side ones"
    assert 2 * g["fd"] < W_OUT - t, "the side bottom flaps do not overlap"
    assert near(g["ya"] + t / 2, LID_TOP), "lid top height"
    assert near(g["yd"] + t / 2, LID_TOP - t), "the dust flaps lie flat under the lid"
    assert near(g["lid"] + t / 2 + SLACK, W_OUT - 1.5 * t), "the tuck flap slides inside the front wall"
    assert g["yd"] - g["hole_top"] >= 15, "board above the hand hole"
    assert g["hole_top"] - HOLE_H - g["ye"] >= 40, "board below the hand hole"
    assert (W_OUT - t - HOLE_W) / 2 >= 40, "board beside the hand hole"
    assert HOLE_W >= TONGUE_W + 20 and HOLE_H >= TONGUE_T + t + 12, "the tongue has room in the hole"
    assert TAG_AREA[0] <= L_OUT and TAG_AREA[1] <= g["lid"], "the lid tags fit the flat lid"
    assert min(g["il"], g["iw"], g["ih"]) - 2 * LINER > 50, "the liner leaves room for the food"


def holes(g: dict[str, float]) -> list[float]:
    """Left side of the hand hole on end 1 and on end 2."""
    return [x + (W_OUT - g["t"] - HOLE_W) / 2 for x in (g["xb"], g["xd"])]


def body_outline(g: dict[str, float]) -> list[tuple[float, float]]:
    xa, xb, xc, xd, xe = (g[k] for k in ("xa", "xb", "xc", "xd", "xe"))
    ys, ye, fd, ya, yb, yd, yt, ov, ti = (g[k] for k in ("ys", "ye", "fd", "ya", "yb", "yd", "yt", "ov", "ti"))
    return [   # counter-clockwise from the bottom of the tab
        (0, ys + TAB_INSET), (xa, ys + TAB_INSET), (xa, ys),
        (xa + ov, ys), (xa + ov, ys - fd), (xb - ov, ys - fd), (xb - ov, ys), (xb, ys), (xb, ye),
        (xb + ov, ye), (xb + ov, ye - fd), (xc - ov, ye - fd), (xc - ov, ye), (xc, ye), (xc, ys),
        (xc + ov, ys), (xc + ov, ys - fd), (xd - ov, ys - fd), (xd - ov, ys), (xd, ys), (xd, ye),
        (xd + ov, ye), (xd + ov, ye - fd), (xe - ov, ye - fd), (xe - ov, ye), (xe, ye),
        (xe, yd), (xe - ov, yd), (xe - ov, yd + DUST), (xd + ov, yd + DUST), (xd + ov, yd), (xd, yd),
        (xd, yb), (xc, yb), (xc, yd), (xc - ov, yd), (xc - ov, yd + DUST), (xb + ov, yd + DUST),
        (xb + ov, yt), (xb - ti, yt), (xb - ti, yt + TUCK), (xa + ti, yt + TUCK), (xa + ti, yt),
        (xa - ov, yt), (xa - ov, ya), (xa, ya), (xa, ya - TAB_INSET), (0, ya - TAB_INSET),
    ]


def body_elements(g: dict[str, float], ox: float = 0.0, oy: float = 0.0) -> tuple[list[str], list[str]]:
    """The blank as SVG elements: cuts and creases. Its left end is at ox and the ground line (y = 0) at oy."""
    xa, xb, xc, xd, xe = (g[k] for k in ("xa", "xb", "xc", "xd", "xe"))
    ys, ye, ya, yd, yt, ov, ti = (g[k] for k in ("ys", "ye", "ya", "yd", "yt", "ov", "ti"))
    cut, fold = [], []
    P = lambda x, y: (ox + x, oy - y)

    def seg(out, x0, y0, x1, y1):
        (a, b), (c, d) = P(x0, y0), P(x1, y1)
        out.append(f'<line x1="{a:.2f}" y1="{b:.2f}" x2="{c:.2f}" y2="{d:.2f}"/>')

    cut.append('<polygon points="' + " ".join("{:.2f},{:.2f}".format(*P(x, y)) for x, y in body_outline(g)) + '"/>')
    seg(cut, xb + ov, yd, xb + ov, yd + DUST)       # between the lid and the dust flap of end 1
    seg(cut, xb, yd, xb + ov, yd)                   # the small corner notch beside it
    seg(cut, xb, yd, xb, ya)
    seg(cut, xb, ya, xb + ov, ya)
    top, bottom = g["hole_top"], g["hole_top"] - HOLE_H
    for x0 in holes(g):                             # hand holes: three cuts and a crease along the top
        seg(cut, x0, top, x0, bottom)
        seg(cut, x0, bottom, x0 + HOLE_W, bottom)
        seg(cut, x0 + HOLE_W, bottom, x0 + HOLE_W, top)
        seg(fold, x0, top, x0 + HOLE_W, top)
    seg(fold, xa, ys + TAB_INSET, xa, ya - TAB_INSET)
    for x in (xb, xc, xd):
        seg(fold, x, ye, x, yd)
    seg(fold, xa + ov, ys, xb - ov, ys)             # bottom flaps
    seg(fold, xb + ov, ye, xc - ov, ye)
    seg(fold, xc + ov, ys, xd - ov, ys)
    seg(fold, xd + ov, ye, xe - ov, ye)
    seg(fold, xb + ov, yd, xc - ov, yd)             # dust flaps
    seg(fold, xd + ov, yd, xe - ov, yd)
    seg(fold, xa, ya, xb, ya)                       # lid hinge
    seg(fold, xa + ti, yt, xb - ti, yt)             # tuck flap
    return cut, fold


def liner_pieces(g: dict[str, float]) -> list[tuple[str, list[tuple[float, float]]]]:
    """Foil bubble pieces, two of each: name and outline from the piece's bottom-left corner."""
    w, d = g["il"] - 2 * SLACK, g["iw"] - 2 * SLACK
    h = g["ih"] - 2 * LINER                         # walls stand on the floor piece, under the lid piece
    ew = g["iw"] - 2 * LINER - 2 * SLACK
    nw = HOLE_W + 20                                # notch that keeps the hand hole clear
    nd = (LID_TOP - g["t"] - LINER) - (g["hole_top"] - HOLE_H) + 5
    n0 = (ew - nw) / 2
    box = lambda a, b: [(0, 0), (a, 0), (a, b), (0, b)]
    return [("FLOOR AND LID", box(w, d)), ("SIDE", box(w, h)),
            ("END", [(0, 0), (ew, 0), (ew, h), (n0 + nw, h), (n0 + nw, h - nd), (n0, h - nd), (n0, h), (0, h)])]


def marks(g: dict[str, float]) -> tuple[list[tuple[float, str]], list[tuple[float, str]]]:
    """Mark-out distances for the blank: along the length from the left end, and up from the bottom edge."""
    xa, xb, xc, xd, xe = (g[k] for k in ("xa", "xb", "xc", "xd", "xe"))
    ys, ye, fd, ya, yb, yd, yt, ov, ti = (g[k] for k in ("ys", "ye", "fd", "ya", "yb", "yd", "yt", "ov", "ti"))
    h1, h2 = holes(g)
    along = [
        (0, "left end: edge of the tab"),
        (xa - ov, "lid, left edge"),
        (xa, "crease 1: tab to side A"),
        (xa + ov, "side A bottom flap, left edge"),
        (xa + ti, "tuck flap, left edge"),
        (xb - ti, "tuck flap, right edge"),
        (xb - ov, "side A bottom flap, right edge"),
        (xb, "crease 2: side A to end 1"),
        (xb + ov, "lid, right edge; end 1 flaps, left edge"),
        (h1, "end 1 hand hole, left side"),
        (h1 + HOLE_W, "end 1 hand hole, right side"),
        (xc - ov, "end 1 flaps, right edge"),
        (xc, "crease 3: end 1 to side B"),
        (xc + ov, "side B bottom flap, left edge"),
        (xd - ov, "side B bottom flap, right edge"),
        (xd, "crease 4: side B to end 2"),
        (xd + ov, "end 2 flaps, left edge"),
        (h2, "end 2 hand hole, left side"),
        (h2 + HOLE_W, "end 2 hand hole, right side"),
        (xe - ov, "end 2 flaps, right edge"),
        (xe, "right end: edge of end 2"),
    ]
    b0 = ys - fd
    up = [(y - b0, name) for y, name in [
        (b0, "bottom edge: side bottom flaps"),
        (ye - fd, "end bottom flaps, bottom edge"),
        (ys, "side walls, bottom crease"),
        (ye, "end walls, bottom crease"),
        (ys + TAB_INSET, "tab, bottom edge"),
        (g["hole_top"] - HOLE_H, "hand holes, bottom edge"),
        (g["hole_top"], "hand holes, top edge (a crease)"),
        (ya - TAB_INSET, "tab, top edge"),
        (yd, "end walls, dust flap crease"),
        (ya, "side A, lid crease"),
        (yb, "side B, top edge"),
        (yd + DUST, "dust flaps, top edge"),
        (yt, "tuck flap crease"),
        (yt + TUCK, "top edge: tuck flap"),
    ]]
    return along, up


def guide(g: dict[str, float]) -> str:
    """The cutting guide as Markdown, from the same numbers as the drawing."""
    t = g["t"]
    along, up = marks(g)
    A = {name: d for d, name in along}
    U = {name: d for d, name in up}
    f = lambda v: f"{v:.1f}"
    length, height = along[-1][0], up[-1][0]
    x_lid0, x1, x_fa0, x_tk0, x_tk1, x_fa1, x2, x_e10, h1a, h1b, x_e11, x3, x_fb0, x_fb1, x4, x_e20, h2a, h2b, x_e21, x_end = \
        [d for d, _ in along[1:]]
    y_ef, y_s, y_e, y_tab0, y_h0, y_h1, y_tab1, y_dust, y_lid, y_front, y_dtop, y_tuck, y_top = [d for d, _ in up[1:]]
    table = lambda rows: "\n".join(f"| {d:.1f} | {name} |" for d, name in rows)
    pieces = liner_pieces(g)
    size = lambda pts: f"{max(x for x, _ in pts):.1f} x {max(y for _, y in pts):.1f}"
    end = pieces[2][1]
    liner = "" if not LINER else f"""
## Liner ({LINER:g} mm foil bubble)

Cut with scissors. Two of each.

| Piece | Size | Goes |
|---|---|---|
| Floor and lid | {size(pieces[0][1])} | One on the floor, one glued under the lid |
| Side | {size(pieces[1][1])} | Along each long wall, standing on the floor piece |
| End | {size(end)} | Between the side pieces at each end |

Cut a notch {end[3][0] - end[6][0]:.0f} wide and {end[3][1] - end[4][1]:.0f} deep in the middle of the top edge of each end piece. It keeps the hand hole clear for the jaw.
"""
    return f"""# Cutting guide: cardboard box with hand holes, {t:g} mm board

Written by `box_pattern.py` from the same numbers as the drawing. All sizes are mm.

The box is one piece. The drone lifts it by a hand hole in each end wall.

## Check the board first

- Thickness: this guide is for {t:g} mm board. If yours differs by more than 0.5 mm, run the script again with your thickness.
- Flutes (the ribs inside the board) run up the walls, across the {f(length)} length of the blank.
- Mark out on the plain inside face. That face ends up inside the box, and every fold goes toward you.
- The drawing ending `_on_wardrobe_box.svg` shows where the blank sits on a 20 x 20 x 34 in wardrobe box. Crease 3 uses one of that box's own corner creases.

## Mark out

Draw a rectangle {f(length)} x {f(height)}. Take every measurement from its left end or its bottom edge.
The four walls sit side by side in a row: tab, side A (back), end 1, side B (front), end 2.

Along the length, from the left end:

| mm | Line |
|---|---|
{table(along)}

Up, from the bottom edge:

| mm | Line |
|---|---|
{table(up)}

## Cut

1. Bottom flaps. Keep four flaps below the walls and cut away the rest:
   side A from {f(x_fa0)} to {f(x_fa1)} and side B from {f(x_fb0)} to {f(x_fb1)}, both from the bottom edge up to {f(y_s)};
   end 1 from {f(x_e10)} to {f(x_e11)} and end 2 from {f(x_e20)} to {f(x_e21)}, both from {f(y_ef)} up to {f(y_e)}.
   That leaves a {f(2 * g['ov'])} wide slot at each of creases 2, 3 and 4.
2. Tab. Keep the strip from the left end to {f(x1)}, between {f(y_tab0)} and {f(y_tab1)} up. Cut away the corners above and below it.
3. Wall tops. Side B ends at {f(y_front)} up. Cut away everything above it between creases 3 and 4.
4. Dust flaps. Above each end wall keep a flap up to {f(y_dtop)}: end 1 from {f(x_e10)} to {f(x_e11)}, end 2 from {f(x_e20)} to {f(x_e21)}.
5. Lid. Above side A keep the lid from {f(x_lid0)} to {f(x_e10)}, up to {f(y_tuck)}, and the tuck flap from {f(x_tk0)} to {f(x_tk1)}, up to the top edge.
6. Lid and dust flap. They share one cut at {f(x_e10)}, from {f(y_dust)} to {f(y_dtop)} up. Cut out the small notch beside it, between {f(x2)} and {f(x_e10)} and between {f(y_dust)} and {f(y_lid)} up, so the lid can close.
7. Hand holes. On each end wall cut the two sides and the bottom of the hole: end 1 from {f(h1a)} to {f(h1b)}, end 2 from {f(h2a)} to {f(h2b)}, between {f(y_h0)} and {f(y_h1)} up. Do not cut the top edge.

## Crease

Press a blunt edge along a ruler on this face. Do not cut through. Every fold goes toward you.

- Creases 1 to 4: up the walls at {f(x1)}, {f(x2)}, {f(x3)} and {f(x4)}.
- Bottom flaps: side A and side B at {f(y_s)} up, end 1 and end 2 at {f(y_e)} up.
- Dust flaps: across each end wall at {f(y_dust)} up.
- Lid: across side A at {f(y_lid)} up.
- Tuck flap: at {f(y_tuck)} up.
- Hand hole flaps: the top edge of each hole, at {f(y_h1)} up.
{liner}
## Fold and fix

1. Fold the four walls into a tube. Glue or tape the tab inside the free edge of end 2.
2. Fold the two end bottom flaps in, then the two side bottom flaps over them. Tape along the seam.
3. Put the liner in, if you use it.
4. Pack the food. Keep the top of each end wall clear for about {TONGUE_REACH:g} mm inside.
5. Fold the two dust flaps in.
6. Close the lid, tuck its flap inside the front wall and tape the front edge.

Leave the hand hole flaps flat. The drone's jaws push them in.

The lid is {f(g['lid'])} deep between its creases. The tags ({TAG_AREA[0]:g} x {TAG_AREA[1]:g}) fit on it. A sticker deeper than the lid needs its white margin trimmed.

## What the gripper needs

| | |
|---|---|
| Hand hole | {HOLE_W:g} x {HOLE_H:g}, centred on each end wall |
| Hole top edge | {HOLE_DROP:g} below the lid top, {g['hole_top']:.1f} above the ground |
| Tongue | up to {TONGUE_W:g} wide and {TONGUE_T:g} thick, reaching {TONGUE_REACH:g} past the wall face |
| End wall faces | {L_OUT:g} apart |
| Lid top | {LID_TOP:g} above the ground |
| Width | {W_OUT:g}, in a {LEG_GAP:g} gap between the landing legs |
"""


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
    for i, s in enumerate([
        f"Medium wardrobe box, 20 x 20 x 34 in, opened flat. Drawn at 1:4, sizes in mm. Board {g['t']:g} mm.",
        "Panel sizes are the nominal ones from the listing. Measure your box before you cut.",
        f"The blank is {xe:.0f} mm long, longer than one panel, so it spans two. Put crease 3 on the corner crease "
        "between them. That crease already folds the right way.",
        "Do not use the corner where the wardrobe box is glued together. Keep hand holes, bar notches and other "
        "creases out of the blank.",
        f"Cut the wardrobe box open along a different corner and remove its flaps. The blank needs {x0 - ox - pw:.0f} mm "
        f"and {ox + 3 * pw - x0 - xe:.0f} mm of spare panel at its two ends.",
    ]):
        label(ox, bottom + fl + 70 + 34 * i, s, 22, "start")
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w / 4:.1f}mm" height="{canvas_h / 4:.1f}mm" viewBox="0 0 {canvas_w:.1f} {canvas_h:.1f}">
<rect width="100%" height="100%" fill="white"/>
<g id="box" stroke="#8d8878" stroke-width="2">{"".join(box)}</g>
<g fill="#ecd9b4" stroke="none">{fill}</g>
<g id="cut" fill="none" stroke="black" stroke-width="1.2">{"".join(cut)}</g>
<g id="crease" fill="none" stroke="#1565c0" stroke-width="1.2" stroke-dasharray="10 6">{"".join(fold)}</g>
<g id="dims" fill="none" stroke="#444" stroke-width="0.9">{"".join(dims)}</g>
<g id="notes" font-family="Helvetica, Arial, sans-serif" fill="#333">{"".join(notes)}</g>
</svg>
'''


def svg(g: dict[str, float]) -> str:
    t = g["t"]
    xa, xb, xc, xd, xe = (g[k] for k in ("xa", "xb", "xc", "xd", "xe"))
    ys, ye, fd, ya, yb, yd, yt, ov = (g[k] for k in ("ys", "ye", "fd", "ya", "yb", "yd", "yt", "ov"))
    low, high = ys - fd, yt + TUCK
    outline = body_outline(g)
    assert min(y for _, y in outline) == low and max(y for _, y in outline) == high
    assert min(x for x, _ in outline) == 0 and max(x for x, _ in outline) == xe

    ox, top = 60.0, 40.0
    oy = top + high                                 # SVG y of the box's ground line
    bottom = oy - low
    pieces = liner_pieces(g) if LINER else []
    kx = ox + xe + 60                               # left edge of the liner column
    width = (kx + max(x for _, pts in pieces for x, _ in pts) if pieces else ox + xe + 30) + 30
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
    for name, x0, x1, hx in [("END 1", xb, xc, holes(g)[0]), ("END 2", xd, xe, holes(g)[1])]:
        mid = x0 + (W_OUT - t) / 2
        text(mid, 62, name)
        text(mid, 52, dim(x1 - x0, yd - ye))
        text(mid, ye - fd / 2, f"FLAP {fd:.1f}", 5)
        text(mid, yd + DUST / 2 - 2, f"DUST FLAP {DUST:g}", 5)
        text(mid, g["hole_top"] + 5, "HAND HOLE: cut 3 sides, crease the top", 4.2)
        chain(dims, notes, [X(x0), X(hx), X(hx + HOLE_W), X(x0 + W_OUT - t)], Y(g["hole_top"] - HOLE_H - 12),
              ["", "hole", ""], reach=0, size=4.2)
    lid_mid = (xa + xb) / 2
    text(lid_mid, ya + g["lid"] / 2 + 8, "LID")
    text(lid_mid, ya + g["lid"] / 2 - 2, dim(xb - xa + 2 * ov, g["lid"]))
    text(lid_mid, ya + g["lid"] / 2 - 14, "the tags go on the other face", 5)
    text(lid_mid, yt + TUCK / 2 - 2, f"TUCK FLAP {TUCK:g}", 5)
    notes.append(f'<text transform="translate({X(xa / 2) + 1.6:.2f} {Y((ys + ya) / 2):.2f}) rotate(-90)" '
                 f'font-size="5" text-anchor="middle">TAB {TAB:g}</text>')

    # dimension chains outside the drawing: the length of every panel between creases and cut edges
    chain(dims, notes, [X(v) for v in (0, xa, xb, xc, xd, xe)], bottom + 12,
          ["tab", "side A", "end 1", "side B", "end 2"])
    chain(dims, notes, [X(0), X(xe)], bottom + 30, ["overall"], reach=0)
    chain(dims, notes, [X(xa - ov), X(xb + ov)], top - 12, ["lid"], reach=-8)
    chain(dims, notes, [Y(v) for v in (high, yt, ya, ys, low)], ox - 14, ["tuck", "lid", "side A", "flap"],
          vertical=True, reach=-8)
    chain(dims, notes, [top, bottom], ox - 34, ["overall"], vertical=True, reach=0)
    chain(dims, notes, [Y(v) for v in (yd + DUST, yd, ye, ye - fd)], X(xe) + 12, ["dust flap", "end wall", "flap"],
          vertical=True)

    foil, ky = [], top
    for name, pts in pieces:
        w, h = max(x for x, _ in pts), max(y for _, y in pts)
        foil.append('<polygon points="' + " ".join(f"{kx + x:.2f},{ky + h - y:.2f}" for x, y in pts) + '"/>')
        notes.append(f'<text x="{kx + w / 2:.2f}" y="{ky + h / 2 + 12:.2f}" font-size="6" text-anchor="middle">LINER {name}, cut 2</text>'
                     f'<text x="{kx + w / 2:.2f}" y="{ky + h / 2 + 22:.2f}" font-size="6" text-anchor="middle">{dim(w, h)}</text>')
        if len(pts) > 4:
            notes.append(f'<text x="{kx + w / 2:.2f}" y="{ky + (pts[3][1] - pts[4][1]) / 2 + 2:.2f}" font-size="4.5" '
                         f'text-anchor="middle">notch {pts[3][0] - pts[6][0]:.0f} x {pts[3][1] - pts[4][1]:.0f}</text>')
        ky += h + 12

    lines = [
        f"Packet cardboard box with hand holes, prototype 2. Board {t:g} mm. All sizes mm, drawn 1:1, "
        "creases at the board mid-plane. This face is the inside of the box.",
        "Solid black: cut. Dashed blue: crease. Every fold goes toward you.",
        "Hand holes: cut the two sides and the bottom, crease the top. Leave the flap flat. The drone's jaw pushes it in.",
        "Fold the walls into a tube and fix the tab inside END 2. Fold the END bottom flaps in first, then the SIDE "
        "flaps, and tape the seam.",
        "Fold the dust flaps in, close the lid, tuck its flap inside SIDE B and tape the front edge.",
        f"Folded: {L_OUT:g} long, {W_OUT:g} wide, {LID_TOP:g} to the lid top. Inside {g['il']:.1f} x {g['iw']:.1f} x "
        f"{g['ih']:.1f}. Blank {xe:.1f} x {high - low:.1f}.",
    ]
    if pieces:
        room = [v - 2 * LINER for v in (g["il"], g["iw"], g["ih"])]
        lines.append(
            f"Green: foil bubble liner, {LINER:g} mm thick, a different material. Cut 2 of each. The notch in the END "
            f"pieces keeps the hand hole clear. Room left for food: {room[0]:.0f} x {room[1]:.0f} x {room[2]:.0f}.")
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
    for key, value in geometry.items():
        print(f"{key:8s} {value:8.2f}")
    print("wrote", out)
