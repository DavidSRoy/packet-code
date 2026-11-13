#!/usr/bin/env python3
"""Cut pattern for a cardboard version of the Packet box (BX-005 body, BX-006 lid).

The gripper jaws close inward and hook under a ledge at each end of the box. Here each
end wall rolls outward into a small tube: the ledge on top, a drop panel with a window
for the hooks, and a return panel whose tabs go back through the wall. The lid sits on
the walls between the two ledges.

  python3 box_pattern.py [board_thickness_mm] [out.svg]

All sizes are mm and the SVG is 1:1. Creases are drawn at the board mid-plane, so a
panel between two creases is its outside size minus one board thickness.
"""
import sys

# Measured from BX-005_print-oriented.stl and BX-006_print-oriented.stl (2026-11-12).
# "From the end" means along the box length, from the outer end of the printed body.
L_OUT = 254.4        # body length over the end cheeks
LID_LEN = 225.6      # lid length
LID_TOP = 154.4      # lid top above the ground (wall top 153.2 plus the 1.2 lid plate)
WALL_OUT = 17.0      # end wall outer face, from the end
LEDGE_EDGE = 4.2     # outer edge of the ledge the jaws hook under, from the end
LEDGE_UNDER = 146.9  # underside of that ledge above the ground
JAW_HALF_W = 80.0    # the ledge is open to the jaws this far each side of the centreline
JAW_REACH = 12.8     # the jaws reach this far below the lid top (backend/tools/sim/lid_camera_sim.py)
W_MAX = 206.0        # width over the lid flaps (lid plate 206.4; the legs leave about 1.7 per side)

# Bench knobs: change these after the first test fit
SLACK = 0.5          # clearance per side where parts slide together
FIT = 2.0            # how far the cardboard ledge underside may sit from the printed one
DROP = 22.0          # drop panel under the ledge, crease to crease
RAIL = 6.0           # strip of the drop panel left under the hook window
FLAP = 25.0          # dust flap length
LID_FLAP = 40.0      # lid side flap depth
TAB_W, TAB_C = 30.0, 45.0   # lock tab width, and its centre offset from the centreline
LINER = 5.0          # foil bubble liner inside the box (0.19 in roll); 0 leaves it out

# The board to cut from: a 20 x 20 x 34 in wardrobe box opened flat (nominal sizes, measure yours)
BOX_PANEL_W, BOX_PANEL_H, BOX_FLAP = 508.0, 864.0, 254.0   # panel width and height, flap depth
BOX_TRIM = 5.0       # stay this far inside each of the box's own creases
BOX_FOOT = 40.0      # gap left below each piece, above the bottom crease


def layout(t: float) -> dict[str, float]:
    body_w = W_MAX - 2 * t - 2 * SLACK
    fx = L_OUT / 2 - WALL_OUT - t / 2
    g = {
        "t": t,
        "body_w": body_w,
        "fx": fx,                            # floor half length, crease (end wall mid-plane)
        "fy": (body_w - t) / 2,              # floor half width, crease
        "sw": fx - t,                        # side wall half length, to the dust flap crease
        "hs": LID_TOP - 1.5 * t,             # side wall, floor crease to top edge (the lid sits on it)
        "he": LID_TOP - 2 * t,               # end wall, floor crease to ledge crease
        "rt": WALL_OUT - LEDGE_EDGE,         # ledge, crease to crease
        "rb": WALL_OUT - LEDGE_EDGE - t / 2,  # return panel, crease to the wall face
        "tab": 3 * t,                        # lock tab length: through the wall, then folded down
        "hem": (L_OUT - LID_LEN) / 2 - SLACK - LEDGE_EDGE + t / 2,   # second layer on top of the ledge
        "under": LID_TOP - 2 * t,            # ledge underside above the ground
        "zb": LID_TOP - 1.5 * t - DROP,      # return panel mid-plane above the ground
        "lid_len": LID_LEN - 2 * SLACK,
        "ly": body_w / 2 + SLACK + t / 2,    # lid half width, crease
        "il": 2 * fx - t,                    # inside length
        "iw": body_w - 2 * t,                # inside width
        "ih": LID_TOP - 2 * t,               # inside height, floor to lid
    }
    check(g)
    return g


def check(g: dict[str, float]) -> None:
    """The folded box must put the jaw ledge and the lid where the printed box has them."""
    t = g["t"]
    near = lambda a, b: abs(a - b) < 1e-6
    assert abs(g["under"] - LEDGE_UNDER) <= FIT, (
        f"{t} mm board puts the ledge underside at {g['under']:.1f}, printed {LEDGE_UNDER}")
    assert near(L_OUT / 2 - (g["fx"] + t / 2), WALL_OUT), "end wall outer face"
    assert near(L_OUT / 2 - (g["fx"] + g["rt"] + t / 2), LEDGE_EDGE), "ledge outer edge"
    assert near(g["fx"] + g["rt"] - g["rb"], g["fx"] + t / 2), "return panel reaches the wall"
    assert near(t / 2 + g["hs"] + t, LID_TOP), "lid top over the side walls"
    assert near(t / 2 + g["he"] + t / 2 + t, LID_TOP), "lid top over the end walls"
    assert near(g["under"] + 2 * t, LID_TOP), "the hem on the ledge is flush with the lid top"
    assert near(2 * (g["ly"] + t / 2), W_MAX), "width over the lid flaps"
    assert g["lid_len"] / 2 > g["fx"] + t / 2, "the lid ends rest on the ledges"
    assert g["zb"] + RAIL < LID_TOP - JAW_REACH - 3, "the hook window is open below the jaws"
    assert g["hem"] + RAIL < DROP, "hem and rail fit in the drop panel"
    assert g["tab"] > t, "lock tabs pass through the wall"
    assert TAB_C + TAB_W / 2 + SLACK < g["fy"] - FLAP, "dust flaps stay off the wall slots"
    assert g["fy"] - JAW_HALF_W >= 8, "cheek strips beside the hook window"
    assert min(g["il"], g["iw"], g["ih"]) - 2 * LINER > 50, "the liner leaves room for the food"


def body_outline(g: dict[str, float]) -> list[tuple[float, float]]:
    t, fx, fy, sw = g["t"], g["fx"], g["fy"], g["sw"]
    top = fy + g["hs"]
    xr = fx + g["he"] + g["rt"] + DROP + g["rb"]     # return panel edge at the wall
    q = [   # one quarter, from the top centre round to the right centre
        (0, top), (sw, top), (sw, top - 1), (sw + FLAP, top - 1), (sw + FLAP, fy + t), (sw, fy + t),
        (sw, fy), (xr, fy),
        (xr, TAB_C + TAB_W / 2), (xr + g["tab"], TAB_C + TAB_W / 2),
        (xr + g["tab"], TAB_C - TAB_W / 2), (xr, TAB_C - TAB_W / 2), (xr, 0),
    ]
    return (q + [(x, -y) for x, y in reversed(q)] + [(-x, -y) for x, y in q]
            + [(-x, y) for x, y in reversed(q)])


def marks(g: dict[str, float]) -> tuple[list[tuple[float, str]], list[tuple[float, str]]]:
    """Mark-out distances for the body blank: along the length from either end, and across
    from either long edge. The blank is the same from both ends and from both long edges."""
    t, fx, fy, sw = g["t"], g["fx"], g["fy"], g["sw"]
    xw = fx + g["he"]
    xl = xw + g["rt"]
    xd = xl + DROP
    xs = fx + g["zb"] - t / 2
    half_x, half_y = xd + g["rb"] + g["tab"], fy + g["hs"]
    along = [(half_x - d, name) for d, name in [
        (half_x, "tab tips, the end of the blank"),
        (xd + g["rb"], "return panel edge"),
        (xd, "crease D, drop to return"),
        (xd - RAIL, "window edge nearer the end"),
        (xl + g["hem"], "hem free edge, the other window edge"),
        (xl, "crease C, ledge to drop, and the hem fold"),
        (xw, "crease B, end wall to ledge"),
        (xs + t / 2 + 0.25, "wall slot edge nearer the end"),
        (xs - t / 2 - 0.25, "wall slot, other edge"),
        (sw + FLAP, "dust flap end"),
        (fx, "crease A, floor to end wall"),
        (sw, "dust flap crease, the end of the side wall"),
        (0, "centre of the blank"),
    ]]
    across = [(half_y - d, name) for d, name in [
        (half_y, "side wall edge, the long edge of the blank"),
        (half_y - 1, "dust flap outer edge"),
        (fy + t, "dust flap inner edge"),
        (fy, "long strip edge, and the floor to side wall crease"),
        (JAW_HALF_W, "window and hem ends"),
        (TAB_C + TAB_W / 2 + SLACK, "wall slot end"),
        (TAB_C + TAB_W / 2, "tab edge"),
        (TAB_C - TAB_W / 2, "tab edge"),
        (TAB_C - TAB_W / 2 - SLACK, "wall slot end"),
        (0, "centre of the blank"),
    ]]
    return along, across


def guide(g: dict[str, float]) -> str:
    """The cutting guide as Markdown, from the same numbers as the drawing."""
    t = g["t"]
    along, across = marks(g)
    x_tab, x_ret, x_d, x_win, x_hem, x_c, x_b, x_s1, x_s2, x_flap, x_a, x_sw, x_mid = [d for d, _ in along]
    y_edge, y_f1, y_f2, y_strip, y_win, y_s1, y_t1, y_t2, y_s2, y_mid = [d for d, _ in across]
    length, width = 2 * x_mid, 2 * y_mid
    lid_w = 2 * (g["ly"] + LID_FLAP)
    table = lambda rows: "\n".join(f"| {d:.1f} | {name} |" for d, name in rows)
    liner = "" if not LINER else f"""
## Liner ({LINER:g} mm foil bubble)

Cut with scissors. Two of each.

| Piece | Size | Goes |
|---|---|---|
| Floor and lid | {g['il'] - 2 * SLACK:.1f} x {g['iw'] - 2 * SLACK:.1f} | One on the floor, one glued under the lid |
| Side | {g['il'] - 2 * SLACK:.1f} x {g['ih'] - 2 * LINER:.1f} | Along each long wall, standing on the floor piece |
| End | {g['iw'] - 2 * LINER - 2 * SLACK:.1f} x {g['ih'] - 2 * LINER:.1f} | Between the side pieces at each end |
"""
    return f"""# Cutting guide: cardboard box, {t:g} mm board

Written by `box_pattern.py` from the same numbers as the drawing. All sizes are mm.

## Check the board first

- Thickness: this guide is for {t:g} mm board. If yours differs by more than 0.5 mm, run the script again with your thickness.
- Flutes (the ribs inside the board) run along the {length:.1f} length of the body.
- Keep old creases, holes and print seams out of every piece.
- Mark out on the plain inside face. That face ends up inside the box.
- The drawing ending `_on_wardrobe_box.svg` shows where the body and lid sit on a 20 x 20 x 34 in wardrobe box.

## Pieces

| Piece | Size | Number |
|---|---|---|
| Body blank | {length:.1f} x {width:.1f} | 1 |
| Lid | {g['lid_len']:.1f} x {lid_w:.1f} | 1 |

## Body: mark out

Draw a rectangle {length:.1f} x {width:.1f}. Take every measurement from an edge of this rectangle.
The blank is the same from both ends and from both long edges, so mark each distance twice.

Along the length, from each end:

| mm | Line |
|---|---|
{table(along)}

Across, from each long edge:

| mm | Line |
|---|---|
{table(across)}

## Body: cut

1. Corners. Cut away the four corner rectangles, each {x_flap:.1f} along the length and {y_strip:.1f} across. This leaves a long strip {width - 2 * y_strip:.1f} wide with a side wall above and below it.
2. Dust flaps. Each side wall keeps a {FLAP:.0f} mm flap at each end, between {x_flap:.1f} and {x_sw:.1f} from the end. Trim 1 mm off the flap's outer edge. Cut out the {t:g} mm notch between the flap and the long strip, from {y_f2:.1f} to {y_strip:.1f} across.
3. Tabs. At each end, cut the long strip back by {x_ret:.1f}, leaving two tabs {TAB_W:.0f} wide. Each tab runs from {y_t1:.1f} to {y_t2:.1f} from a long edge.
4. Hook window. At each end, cut out the slot between {x_win:.1f} and {x_hem:.1f} from the end. It runs from {y_win:.1f} from one long edge to {y_win:.1f} from the other ({width - 2 * y_win:.1f} long).
5. Hem sides. From each end of that slot, cut straight on to crease C: two cuts per end, from {x_hem:.1f} to {x_c:.1f} from the end.
6. Wall slots. Two per end, between {x_s1:.1f} and {x_s2:.1f} from the end. Each runs from {y_s1:.1f} to {y_s2:.1f} from a long edge.

## Body: crease

Press a blunt edge along a ruler. Do not cut through.

Fold toward you, so score this face:

- Floor to side walls: the two long strip edges, only between the side wall ends ({x_sw:.1f} from each end).
- Crease A: {x_a:.1f} from each end, across the long strip.
- Dust flaps: {x_sw:.1f} from each end, across each flap.
- Hem: crease C, {x_c:.1f} from each end, only across the window.

Fold away from you, so turn the board over and score the back:

- Crease B: {x_b:.1f} from each end, across the long strip.
- Crease C beside the window: the two short lengths between the strip edge and the window.
- Crease D: {x_d:.1f} from each end, across the long strip.

## Lid

Cut a rectangle {g['lid_len']:.1f} x {lid_w:.1f}. Score two lines along the {g['lid_len']:.1f} direction, {LID_FLAP:.0f} in from each long edge, and fold both flaps toward you. The face you scored is the underside.
{liner}
## Fold and fix

1. Fold the two side walls up.
2. Fold the four dust flaps in.
3. Fold the end walls up outside the dust flaps and tape the flaps to them.
4. At each end fold the ledge out and the drop panel down.
5. Fold the return panel in, push the two tabs through the wall slots, fold them down inside and tape them.
6. Fold each hem up and back onto its ledge and glue it flat.
7. Fold the lid flaps down and set the lid between the two ledges.
"""


def body_elements(g: dict[str, float], cx: float = 0.0, cy: float = 0.0) -> tuple[list[str], list[str], list[str]]:
    """The body blank as SVG elements centred on (cx, cy): cuts, creases folding toward you,
    creases folding away."""
    t, fx, fy, sw = g["t"], g["fx"], g["fy"], g["sw"]
    xw = fx + g["he"]                   # wall to ledge crease
    xl = xw + g["rt"]                   # ledge to drop crease
    xd = xl + DROP                      # drop to return crease
    xs = fx + g["zb"] - t / 2           # wall slot centre: the return panel mid-plane, up the wall
    half_y = fy + g["hs"]
    cut, toward, away = [], [], []
    X = lambda x: f"{cx + x:.2f}"
    Y = lambda y: f"{cy - y:.2f}"

    def line(out, xa, ya, xb, yb):
        out.append(f'<line x1="{X(xa)}" y1="{Y(ya)}" x2="{X(xb)}" y2="{Y(yb)}"/>')

    def rect(out, xa, ya, xb, yb):
        out.append(f'<rect x="{X(min(xa, xb))}" y="{Y(max(ya, yb))}" '
                   f'width="{abs(xb - xa):.2f}" height="{abs(yb - ya):.2f}"/>')

    cut.append('<polygon points="' + " ".join(f"{X(x)},{Y(y)}" for x, y in body_outline(g)) + '"/>')
    jw = JAW_HALF_W
    for sx in (1, -1):
        rect(cut, sx * (xl + g["hem"]), -jw, sx * (xd - RAIL), jw)           # hook window
        for s in (1, -1):
            line(cut, sx * xl, s * jw, sx * (xl + g["hem"]), s * jw)         # hem flap sides
            rect(cut, sx * (xs - t / 2 - 0.25), s * (TAB_C - TAB_W / 2 - SLACK),
                 sx * (xs + t / 2 + 0.25), s * (TAB_C + TAB_W / 2 + SLACK))  # wall slot for a lock tab
            line(toward, sx * sw, s * (fy + t), sx * sw, s * (half_y - 1))   # dust flap
            line(away, sx * xl, s * jw, sx * xl, s * fy)                     # ledge to drop, beside the window
        line(toward, sx * fx, -fy, sx * fx, fy)                              # floor to end wall
        line(toward, sx * xl, -jw, sx * xl, jw)                              # hem, folds back onto the ledge
        line(away, sx * xw, -fy, sx * xw, fy)                                # end wall to ledge
        line(away, sx * xd, -fy, sx * xd, fy)                                # drop to return
        line(toward, -sw, sx * fy, sw, sx * fy)                              # floor to side wall
    return cut, toward, away


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
    """The body and lid laid over a wardrobe box opened flat, drawn at 1:4."""
    along, across = marks(g)
    length, width = 2 * along[-1][0], 2 * across[-1][0]       # the body runs up the panel, so its width goes across
    lid_w, lid_len = 2 * (g["ly"] + LID_FLAP), g["lid_len"]
    pw, ph, fl = BOX_PANEL_W, BOX_PANEL_H, BOX_FLAP
    assert width + 2 * BOX_TRIM <= pw, f"the body is {width:.1f} wide, the trimmed panel only {pw - 2 * BOX_TRIM:.1f}"
    assert length + BOX_FOOT <= ph and lid_len + BOX_FOOT <= ph and lid_w + 2 * BOX_TRIM <= pw, "pieces fit the panel"

    ox, oy = 150.0, 120.0
    top, bottom = oy + fl, oy + fl + ph                       # the creases above and below the panels
    canvas_w, canvas_h = ox + 4 * pw + 80, bottom + fl + 250
    box, dims, notes = [], [], []
    for i in range(4):
        x = ox + i * pw
        box.append(f'<rect x="{x:.1f}" y="{oy:.1f}" width="{pw:.1f}" height="{fl:.1f}" fill="#f1eee6" stroke-dasharray="14 10"/>'
                   f'<rect x="{x:.1f}" y="{bottom:.1f}" width="{pw:.1f}" height="{fl:.1f}" fill="#f1eee6" stroke-dasharray="14 10"/>'
                   f'<rect x="{x:.1f}" y="{top:.1f}" width="{pw:.1f}" height="{ph:.1f}" fill="white"/>')
    label = lambda x, y, s, size=22, anchor="middle": notes.append(
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}">{s}</text>')
    for i, s in enumerate(["PANEL 1: spare", "PANEL 2: body", "PANEL 3: lid", "PANEL 4: spare"]):
        label(ox + (i + 0.5) * pw, top + 44, s)
    label(ox + 1.5 * pw, oy + fl / 2 + 8, "top flaps: cut off along the crease")
    label(ox + 0.5 * pw, bottom + fl - 30, "bottom flaps: cut off along the crease", 18)
    label(ox + 3.5 * pw, top + ph / 2, "&#8593; flutes run this way &#8595;")
    label(ox + 0.5 * pw, top + ph / 2, "room for a second body")

    bx, by = ox + 1.5 * pw, bottom - BOX_FOOT - length / 2    # body centre, its length running up the panel
    cut, toward, away = body_elements(g)
    fill = '<polygon points="' + " ".join(f"{x:.2f},{-y:.2f}" for x, y in body_outline(g)) + '"/>'
    lxc, lyc = ox + 2.5 * pw, bottom - BOX_FOOT - lid_len / 2  # lid centre, same direction
    lid = (f'<rect x="{lxc - lid_w / 2:.2f}" y="{lyc - lid_len / 2:.2f}" width="{lid_w:.2f}" height="{lid_len:.2f}"/>')
    lid_creases = "".join(f'<line x1="{lxc + s * g["ly"]:.2f}" y1="{lyc - lid_len / 2:.2f}" '
                          f'x2="{lxc + s * g["ly"]:.2f}" y2="{lyc + lid_len / 2:.2f}"/>' for s in (1, -1))
    label(lxc, lyc + 8, "LID")

    big = dict(size=16.0, reach=0.0)
    chain(dims, notes, [ox + i * pw for i in range(5)], oy - 30, ["panel"] * 4, **big)
    chain(dims, notes, [oy, top, bottom, bottom + fl], ox - 40, ["flap", "panel", "flap"], vertical=True, **big)
    side = (pw - width) / 2
    chain(dims, notes, [ox + pw, bx - width / 2, bx + width / 2, ox + 2 * pw], bottom + 70, ["", "body", ""], **big)
    chain(dims, notes, [top, by - length / 2, by + length / 2, bottom], ox + pw - 60, ["clear", "body", "foot"],
          vertical=True, **big)
    chain(dims, notes, [ox + 2 * pw, lxc - lid_w / 2, lxc + lid_w / 2, ox + 3 * pw], bottom + 70, ["", "lid", ""], **big)
    chain(dims, notes, [top, lyc - lid_len / 2, lyc + lid_len / 2, bottom], lxc + lid_w / 2 + 50,
          ["clear", "lid", "foot"], vertical=True, **big)
    for i, s in enumerate([
        f"Medium wardrobe box, 20 x 20 x 34 in, opened flat. Drawn at 1:4, sizes in mm. Board {g['t']:g} mm.",
        "Panel sizes are the nominal ones from the listing. Measure your box before you cut.",
        f"Cut along the box's own creases, then trim {BOX_TRIM:g} mm inside each one. That leaves "
        f"{pw - 2 * BOX_TRIM:.0f} mm for the {width:.1f} mm body, {side - BOX_TRIM:.1f} mm to spare each side.",
        f"Keep hand holes, bar notches and old creases out of both pieces. The panel is {ph - length:.0f} mm longer "
        "than the body, so slide the body up if the bottom is damaged.",
    ]):
        label(ox, bottom + fl + 70 + 34 * i, s, 22, "start")
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w / 4:.1f}mm" height="{canvas_h / 4:.1f}mm" viewBox="0 0 {canvas_w:.1f} {canvas_h:.1f}">
<rect width="100%" height="100%" fill="white"/>
<g id="box" stroke="#8d8878" stroke-width="2">{"".join(box)}</g>
<g transform="translate({bx:.2f} {by:.2f}) rotate(90)">
<g fill="#ecd9b4" stroke="none">{fill}</g>
<g fill="none" stroke="black" stroke-width="1.2">{"".join(cut)}</g>
<g fill="none" stroke="#1565c0" stroke-width="1.2" stroke-dasharray="10 6">{"".join(toward)}</g>
<g fill="none" stroke="#e65100" stroke-width="1.2" stroke-dasharray="14 5 3 5">{"".join(away)}</g>
</g>
<g fill="#ecd9b4" stroke="black" stroke-width="1.2">{lid}</g>
<g fill="none" stroke="#1565c0" stroke-width="1.2" stroke-dasharray="10 6">{lid_creases}</g>
<g id="dims" fill="none" stroke="#444" stroke-width="0.9">{"".join(dims)}</g>
<g id="notes" font-family="Helvetica, Arial, sans-serif" fill="#333">{"".join(notes)}</g>
</svg>
'''


def svg(g: dict[str, float]) -> str:
    t, fx, fy, sw = g["t"], g["fx"], g["fy"], g["sw"]
    xw = fx + g["he"]                   # wall to ledge crease
    xl = xw + g["rt"]                   # ledge to drop crease
    xd = xl + DROP                      # drop to return crease
    half_x, half_y = xd + g["rb"] + g["tab"], fy + g["hs"]
    outline = body_outline(g)
    assert max(x for x, _ in outline) == half_x and max(y for _, y in outline) == half_y

    m = 40.0
    cx, cy = m + half_x, 60 + half_y
    lx = cx + half_x + 50 + g["lid_len"] / 2        # lid centre
    lid_hy = g["ly"] + LID_FLAP
    liner = [] if not LINER else [      # name, length, height; two of each
        ("LINER FLOOR AND LID", g["il"] - 2 * SLACK, g["iw"] - 2 * SLACK),
        ("LINER SIDE", g["il"] - 2 * SLACK, g["ih"] - 2 * LINER),
        ("LINER END", g["iw"] - 2 * LINER - 2 * SLACK, g["ih"] - 2 * LINER),
    ]
    kx = lx + g["lid_len"] / 2 + 50     # left edge of the liner column
    width = (kx + liner[0][1] if liner else lx + g["lid_len"] / 2) + m
    height = cy + half_y + 170

    cut, toward, away = body_elements(g, cx, cy)
    notes: list[str] = []
    X = lambda x, ox=cx: f"{ox + x:.2f}"
    Y = lambda y: f"{cy - y:.2f}"

    def text(x, y, s, ox=cx, size=6.0):
        notes.append(f'<text x="{X(x, ox)}" y="{Y(y)}" font-size="{size}" text-anchor="middle">{s}</text>')

    for s in (1, -1):                   # lid flap creases, then the lid outline
        toward.append(f'<line x1="{X(-g["lid_len"] / 2, lx)}" y1="{Y(s * g["ly"])}" '
                      f'x2="{X(g["lid_len"] / 2, lx)}" y2="{Y(s * g["ly"])}"/>')
    cut.append(f'<rect x="{X(-g["lid_len"] / 2, lx)}" y="{Y(lid_hy)}" '
               f'width="{g["lid_len"]:.2f}" height="{2 * lid_hy:.2f}"/>')

    dim = lambda a, b: f"{a:.1f} x {b:.1f}"
    text(0, 8, "FLOOR")
    text(0, -2, dim(2 * fx, 2 * fy))
    text(0, -22, "&#8592; flutes run along the length &#8594;")
    for s in (1, -1):
        text(0, s * (fy + g["hs"] / 2) + 4, "SIDE WALL")
        text(0, s * (fy + g["hs"] / 2) - 6, dim(2 * sw, g["hs"]))
        text(s * (fx + g["he"] / 2 - 15), 8, "END WALL")
        text(s * (fx + g["he"] / 2 - 15), -2, dim(g["he"], 2 * fy))
        text(s * (xl + 6), 6, "HEM", size=4)
        text(s * (xl + 6), 0, f"{g['hem']:.1f}", size=4)
        ex = s * (xw + 18)
        text(ex, fy + 58, f"LEDGE {g['rt']:.1f}", size=5)
        text(ex, fy + 51, f"DROP {DROP:.1f}", size=5)
        text(ex, fy + 44, f"RETURN {g['rb']:.1f}", size=5)
        text(ex, fy + 37, f"tabs {g['tab']:.0f} x {TAB_W:.0f}", size=5)
        text(s * (sw + FLAP + 22), fy + g["hs"] / 2, f"FLAP {FLAP:.0f}", size=5)
        text(s * (sw + FLAP + 22), -(fy + g["hs"] / 2), f"FLAP {FLAP:.0f}", size=5)
        text(0, s * (g["ly"] + LID_FLAP / 2) - 2, f"LID FLAP {LID_FLAP:.0f}", lx)
    text(0, 8, "LID", lx)
    text(0, -2, dim(g["lid_len"], 2 * g["ly"]), lx)

    foil, ky = [], cy - half_y
    for name, w, h in liner:
        foil.append(f'<rect x="{kx:.2f}" y="{ky:.2f}" width="{w:.2f}" height="{h:.2f}"/>')
        notes.append(f'<text x="{kx + w / 2:.2f}" y="{ky + h / 2 - 2:.2f}" font-size="6" text-anchor="middle">{name}, cut 2</text>'
                     f'<text x="{kx + w / 2:.2f}" y="{ky + h / 2 + 8:.2f}" font-size="6" text-anchor="middle">{dim(w, h)}</text>')
        ky += h + 12

    # mark-out distances at the left end: along the length above the strip, across beside it
    along, across = marks(g)
    for d, _ in along[:9]:
        px, py = cx - half_x + d, cy - fy
        notes.append(f'<line x1="{px:.2f}" y1="{py - 1:.2f}" x2="{px:.2f}" y2="{py - 7:.2f}" stroke="#888" stroke-width="0.2"/>'
                     f'<text transform="translate({px + 1.2:.2f} {py - 9:.2f}) rotate(-90)" font-size="3.5" fill="#666">{d:.1f}</text>')
    for d, name in across[3:]:
        if "slot" in name:              # half a millimetre from the tab edges: the labels would overlap
            continue
        px, py = cx - half_x, cy - half_y + d
        notes.append(f'<line x1="{px - 2:.2f}" y1="{py:.2f}" x2="{px - 8:.2f}" y2="{py:.2f}" stroke="#888" stroke-width="0.2"/>'
                     f'<text x="{px - 10:.2f}" y="{py + 1.2:.2f}" font-size="3.5" fill="#666" text-anchor="end">{d:.1f}</text>')
    # dimension chains outside the drawing: the length of every panel between cut points and creases
    dims: list[str] = []
    left, top, right, bottom = cx - half_x, cy - half_y, cx + half_x, cy + half_y
    a = [along[i][0] for i in (0, 1, 2, 5, 6, 10)]          # end, return, creases D, C, B, A
    run = [left + d for d in a] + [right - d for d in reversed(a)]
    ends = ["tab", "return", "drop", "ledge", "end wall"]
    chain(dims, notes, run, bottom + 10, ends + ["floor"] + ends[::-1])
    chain(dims, notes, [left, right], bottom + 50, ["overall"], reach=0)
    b = [along[i][0] for i in (0, 9, 11)]                   # end, dust flap end, side wall end
    chain(dims, notes, [left + d for d in b] + [right - d for d in reversed(b)], top - 10,
          ["cut away", "flap", "side wall", "flap", "cut away"], reach=-8)
    c = [across[0][0], across[3][0]]                        # long edge, strip edge
    chain(dims, notes, [top + d for d in c] + [bottom - d for d in reversed(c)], right + 10,
          ["side wall", "floor", "side wall"], vertical=True)
    chain(dims, notes, [top, bottom], right + 26, ["overall"], vertical=True, reach=0)
    lid_l, lid_r, lid_t = lx - g["lid_len"] / 2, lx + g["lid_len"] / 2, cy - lid_hy
    chain(dims, notes, [lid_l, lid_r], cy + lid_hy + 10, ["lid"])
    chain(dims, notes, [lid_t, lid_t + LID_FLAP, cy + lid_hy - LID_FLAP, cy + lid_hy], lid_r + 10,
          ["flap", "lid", "flap"], vertical=True)
    chain(dims, notes, [lid_t, cy + lid_hy], lid_r + 26, ["overall"], vertical=True, reach=0)

    inside = (g["il"], g["iw"], g["ih"])
    base = -half_y - 66
    lines = [
        f"Packet cardboard box, prototype 1 (BX-005 / BX-006). Board {t:g} mm. All sizes mm, drawn 1:1, "
        "creases at the board mid-plane. This face is the inside of the box.",
        "Solid black: cut. Dashed blue: crease, fold toward you. Dash-dot orange: crease, fold away from you "
        "(score it on the back).",
        "Each end: fold the wall up, the ledge out, the drop panel down and the return panel in. Push the tabs "
        "through the wall slots, fold them down and tape them.",
        "HEM: fold it up and back so it lies on top of the ledge, then glue it. It is the second layer of the "
        "ledge the jaws lift on. Tape the dust flaps to the end walls.",
        "Small grey numbers at the left end: distance from the left end along the length, and from the top long "
        "edge across. The right end and the bottom half mirror them. The cutting guide lists every mark.",
        f"Folded: {L_OUT - 2 * LEDGE_EDGE:.1f} long, {g['body_w']:.1f} wide ({W_MAX:.1f} over the lid flaps), "
        f"{LID_TOP} to the lid top. Inside {inside[0]:.1f} x {inside[1]:.1f} x {inside[2]:.1f}. "
        f"Blank: body {2 * half_x:.1f} x {2 * half_y:.1f}, lid {g['lid_len']:.1f} x {2 * lid_hy:.1f}.",
    ]
    if liner:
        left = [v - 2 * LINER for v in inside]
        lines.append(
            f"Green: foil bubble liner, {LINER:g} mm thick, a different material. Cut 2 of each. Tape the floor, sides "
            f"and ends inside the box and glue the last piece under the lid. Room left for food: "
            f"{left[0]:.0f} x {left[1]:.0f} x {left[2]:.0f}.")
    for i, s in enumerate(lines):
        notes.append(f'<text x="{m}" y="{Y(base - 12 * i)}" font-size="6">{s}</text>')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}mm" height="{height:.0f}mm" viewBox="0 0 {width:.0f} {height:.0f}">
<rect width="100%" height="100%" fill="white"/>
<g id="cut" fill="none" stroke="black" stroke-width="0.4">{"".join(cut)}</g>
<g id="crease-toward" fill="none" stroke="#1565c0" stroke-width="0.4" stroke-dasharray="4 2">{"".join(toward)}</g>
<g id="crease-away" fill="none" stroke="#e65100" stroke-width="0.4" stroke-dasharray="6 2 1 2">{"".join(away)}</g>
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
