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
LINER = 8.0          # foil bubble liner inside the box (5/16 in thick); 0 leaves it out


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


def svg(g: dict[str, float]) -> str:
    t, fx, fy, sw = g["t"], g["fx"], g["fy"], g["sw"]
    xw = fx + g["he"]                   # wall to ledge crease
    xl = xw + g["rt"]                   # ledge to drop crease
    xd = xl + DROP                      # drop to return crease
    xs = fx + g["zb"] - t / 2           # wall slot centre: the return panel mid-plane, up the wall
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
    height = cy + half_y + 125

    cut, toward, away, notes = [], [], [], []
    X = lambda x, ox=cx: f"{ox + x:.2f}"
    Y = lambda y: f"{cy - y:.2f}"

    def line(out, xa, ya, xb, yb, ox=cx):
        out.append(f'<line x1="{X(xa, ox)}" y1="{Y(ya)}" x2="{X(xb, ox)}" y2="{Y(yb)}"/>')

    def rect(out, xa, ya, xb, yb, ox=cx):
        out.append(f'<rect x="{X(min(xa, xb), ox)}" y="{Y(max(ya, yb))}" '
                   f'width="{abs(xb - xa):.2f}" height="{abs(yb - ya):.2f}"/>')

    def text(x, y, s, ox=cx, size=6.0):
        notes.append(f'<text x="{X(x, ox)}" y="{Y(y)}" font-size="{size}" text-anchor="middle">{s}</text>')

    cut.append('<polygon points="' + " ".join(f"{X(x)},{Y(y)}" for x, y in outline) + '"/>')
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
        line(toward, -g["lid_len"] / 2, sx * g["ly"], g["lid_len"] / 2, sx * g["ly"], lx)   # lid flap
    rect(cut, -g["lid_len"] / 2, -lid_hy, g["lid_len"] / 2, lid_hy, lx)

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
        text(ex, fy + 30, f"LEDGE {g['rt']:.1f}", size=5)
        text(ex, fy + 23, f"DROP {DROP:.1f}", size=5)
        text(ex, fy + 16, f"RETURN {g['rb']:.1f}", size=5)
        text(ex, fy + 9, f"tabs {g['tab']:.0f} x {TAB_W:.0f}", size=5)
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
        ky += h + 20

    stations = [0, g["tab"], g["tab"] + g["rb"], half_x - xl, half_x - xw, half_x - fx, half_x - sw, half_x]
    inside = (g["il"], g["iw"], g["ih"])
    base = -half_y - 22
    lines = [
        f"Packet cardboard box, prototype 1 (BX-005 / BX-006). Board {t:g} mm. All sizes mm, drawn 1:1, "
        "creases at the board mid-plane. This face is the inside of the box.",
        "Solid black: cut. Dashed blue: crease, fold toward you. Dash-dot orange: crease, fold away from you "
        "(score it on the back).",
        "Each end: fold the wall up, the ledge out, the drop panel down and the return panel in. Push the tabs "
        "through the wall slots, fold them down and tape them.",
        "HEM: fold it up and back so it lies on top of the ledge, then glue it. It is the second layer of the "
        "ledge the jaws lift on. Tape the dust flaps to the end walls.",
        "Marks along the length from the left edge to the centre: " + " | ".join(f"{s:.1f}" for s in stations)
        + f". Across from the top edge: 0 | {g['hs']:.1f} | {half_y:.1f} (centre). All four quarters are the same.",
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
<g id="notes" font-family="Helvetica, Arial, sans-serif" fill="#333">{"".join(notes)}</g>
</svg>
'''


if __name__ == "__main__":
    thickness = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    out = sys.argv[2] if len(sys.argv) > 2 else f"packet_box_cardboard_t{thickness:g}.svg"
    geometry = layout(thickness)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg(geometry))
    for key, value in geometry.items():
        print(f"{key:8s} {value:8.2f}")
    print("wrote", out)
