#!/usr/bin/env python3
"""Cut pattern for a cardboard version of the Packet box (BX-005 / BX-006 envelope).

The two end walls roll over into hollow rims. The lid sits between the rims and the
gripper fingers drop into slots in the rim tops.

  python3 box_pattern.py [board_thickness_mm] [out.svg]

All sizes are mm and the SVG is 1:1. Creases are drawn at the board mid-plane, so a
panel between two creases is its outside size minus one board thickness.
"""
import sys

# Measured from the CAD (Master Assembly v60, see backend/tools/sim/lid_camera_sim.py)
L_OUT = 254.4       # body outside length
H_OUT = 155.2       # height with the lid on
LID_LEN = 225.6     # lid top length = opening between the two rims
W_MAX = 206.0       # width over the lid flaps (CAD 206.4; the legs leave about 1.7 per side)
JAW_REACH = 12.8    # fingers reach this far below the lid top
JAW_HALF_W = 60.0   # the jaws sit within this of the centreline

# Bench knobs: change these after the first test fit
SLACK = 0.5         # clearance per side where parts slide together
JAW_MARGIN = 2.0    # slot margin past the jaws, each side
FLAP = 25.0         # dust flap length
LID_FLAP = 40.0     # lid side flap depth
TAB_W, TAB_C = 40.0, 50.0   # lock tab width, and its centre offset from the centreline
WINDOW = 20.0       # depth of the optional window in the inner panel


def layout(t: float) -> dict[str, float]:
    rim = (L_OUT - LID_LEN) / 2
    body_w = W_MAX - 2 * t - 2 * SLACK
    g = {
        "t": t,
        "rim": rim,
        "hollow": rim - 2 * t,          # clear gap inside the rim
        "body_w": body_w,
        "fx": (L_OUT - t) / 2,          # floor half length, crease
        "fy": (body_w - t) / 2,         # floor half width, crease
        "sw": (L_OUT - t) / 2 - t,      # side wall half length, to the dust flap crease
        "hs": H_OUT - 1.5 * t,          # side wall, floor crease to top edge
        "ho": H_OUT - t,                # end wall outer panel, crease to crease
        "rt": rim - t,                  # rim top, crease to crease
        "hi": H_OUT - 1.5 * t,          # end wall inner panel, rim crease to floor
        "iy": body_w / 2 - t - SLACK,   # inner panel half width
        "sy": JAW_HALF_W + JAW_MARGIN,  # jaw slot half length
        "lid_len": LID_LEN - 2 * SLACK,
        "ly": body_w / 2 + SLACK + t / 2,   # lid half width, crease
    }
    check(g)
    return g


def check(g: dict[str, float]) -> None:
    """The folded box must come back to the CAD envelope."""
    t = g["t"]
    near = lambda a, b: abs(a - b) < 1e-6
    assert g["hollow"] > 0, f"board {t} mm is too thick for a {g['rim']} mm rim"
    assert near(2 * (g["fx"] + t / 2), L_OUT), "outside length"
    assert near(t / 2 + g["ho"] + t / 2, H_OUT), "height at the rim"
    assert near(t / 2 + g["hs"] + t, H_OUT), "side wall plus lid is flush with the rim"
    assert near(2 * (g["fx"] - g["rt"] - t / 2), LID_LEN), "opening between the rims"
    assert near((H_OUT - t / 2) - g["hi"], t), "inner panel lands on the floor"
    assert near(2 * (g["ly"] + t / 2), W_MAX), "width over the lid flaps"
    assert near(g["iy"] + SLACK, g["fy"] - t / 2), "inner panel fits between the side walls"
    assert g["fy"] - FLAP > g["sy"], "dust flaps stay out of the jaw slot"
    assert g["hi"] > JAW_REACH + t, "pocket is deeper than the finger reach"
    assert TAB_C + TAB_W / 2 < g["iy"], "lock tabs are on the inner panel"


def body_outline(g: dict[str, float]) -> list[tuple[float, float]]:
    t, fx, fy, sw = g["t"], g["fx"], g["fy"], g["sw"]
    top = fy + g["hs"]
    x1 = fx + g["ho"] + g["rt"]         # second rim crease
    x2 = x1 + g["hi"]                   # inner panel bottom edge
    q = [   # one quarter, from the top centre round to the right centre
        (0, top), (sw, top), (sw, top - 1), (sw + FLAP, top - 1), (sw + FLAP, fy + t), (sw, fy + t),
        (sw, fy), (fx, fy), (x1, fy), (x1, g["iy"]), (x2, g["iy"]),
        (x2, TAB_C + TAB_W / 2), (x2 + t, TAB_C + TAB_W / 2), (x2 + t, TAB_C - TAB_W / 2),
        (x2, TAB_C - TAB_W / 2), (x2, 0),
    ]
    return (q + [(x, -y) for x, y in reversed(q)] + [(-x, -y) for x, y in q]
            + [(-x, y) for x, y in reversed(q)])


def svg(g: dict[str, float]) -> str:
    t, fx, fy, sw, sy = g["t"], g["fx"], g["fy"], g["sw"], g["sy"]
    x0 = fx + g["ho"]                   # first rim crease
    x1 = x0 + g["rt"]                   # second rim crease
    half_x, half_y = x1 + g["hi"] + t, fy + g["hs"]
    outline = body_outline(g)
    assert max(x for x, _ in outline) == half_x and max(y for _, y in outline) == half_y

    m = 40.0
    cx, cy = m + half_x, 60 + half_y
    lx = cx + half_x + 50 + g["lid_len"] / 2        # lid centre
    lid_hy = g["ly"] + LID_FLAP
    width, height = lx + g["lid_len"] / 2 + m, cy + half_y + 110

    cut, crease, opt, notes = [], [], [], []
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
    slot0, slot1 = x0 + t / 2, x1 - t / 2      # the panel faces sit half a board inside each crease
    assert abs((slot1 - slot0) - g["hollow"]) < 1e-6, "jaw slot spans the hollow"
    for sx in (1, -1):
        rect(cut, sx * slot0, -sy, sx * slot1, sy)                           # jaw slot in the rim top
        rect(opt, sx * x1, -sy, sx * (x1 + WINDOW), sy)                      # optional inner window
        sc = sx * (fx - g["rt"])                                             # inner panel mid-plane
        for s in (1, -1):
            rect(cut, sc - t / 2 - 0.25, s * (TAB_C - TAB_W / 2 - SLACK),
                 sc + t / 2 + 0.25, s * (TAB_C + TAB_W / 2 + SLACK))         # floor slot for a lock tab
            line(crease, sx * sw, s * (fy + t), sx * sw, s * (half_y - 1))   # dust flap
        line(crease, sx * fx, -fy, sx * fx, fy)                              # floor to end wall
        line(crease, sx * x0, -fy, sx * x0, fy)                              # rim, outer
        line(crease, sx * x1, -g["iy"], sx * x1, g["iy"])                    # rim, inner
        line(crease, -sw, sx * fy, sw, sx * fy)                              # floor to side wall
        line(crease, -g["lid_len"] / 2, sx * g["ly"], g["lid_len"] / 2, sx * g["ly"], lx)   # lid flap
    rect(cut, -g["lid_len"] / 2, -lid_hy, g["lid_len"] / 2, lid_hy, lx)

    dim = lambda a, b: f"{a:.1f} x {b:.1f}"
    text(0, 8, "FLOOR")
    text(0, -2, dim(2 * fx, 2 * fy))
    text(0, -22, "&#8592; flutes run along the length &#8594;")
    for s in (1, -1):
        text(0, s * (fy + g["hs"] / 2) + 4, "SIDE WALL")
        text(0, s * (fy + g["hs"] / 2) - 6, dim(2 * sw, g["hs"]))
        text(s * (fx + g["ho"] / 2), 8, "END WALL, OUTER")
        text(s * (fx + g["ho"] / 2), -2, dim(g["ho"], 2 * fy))
        text(s * (x1 + g["hi"] / 2 + 10), 8, "END WALL, INNER")
        text(s * (x1 + g["hi"] / 2 + 10), -2, dim(g["hi"], 2 * g["iy"]))
        text(s * (x1 + WINDOW / 2), 75, "optional", size=4)
        text(s * (x0 + g["rt"] / 2), fy + 16, f"RIM TOP {g['rt']:.1f}")
        text(s * (x0 + g["rt"] / 2), fy + 8, f"slot {g['hollow']:.1f} x {2 * sy:.0f}", size=5)
        text(s * (sw + FLAP + 22), fy + g["hs"] / 2, f"FLAP {FLAP:.0f}", size=5)
        text(s * (sw + FLAP + 22), -(fy + g["hs"] / 2), f"FLAP {FLAP:.0f}", size=5)
        text(0, s * (g["ly"] + LID_FLAP / 2) - 2, f"LID FLAP {LID_FLAP:.0f}", lx)
    text(0, 8, "LID", lx)
    text(0, -2, dim(g["lid_len"], 2 * g["ly"]), lx)

    stations = [0, t, t + g["hi"], t + g["hi"] + g["rt"], half_x - fx, half_x - sw, half_x]
    base = -half_y - 22
    for i, s in enumerate([
        f"Packet cardboard box, prototype 0. Board {t:g} mm. All sizes mm, drawn 1:1, creases at the board mid-plane.",
        "Solid black: cut. Dashed blue: crease, scored on this face (the inside); every fold goes toward you. "
        "Dashed red: cut only if the jaw finger does not fit the slot.",
        "Marks along the length from the left edge to the centre: " + " | ".join(f"{s:.1f}" for s in stations)
        + f". Across from the top edge: 0 | {g['hs']:.1f} | {half_y:.1f} (centre). The pattern is the same in all four quarters.",
        f"Folded: {L_OUT} long, {g['body_w']:.1f} wide ({W_MAX:.1f} over the lid flaps), {H_OUT} tall. "
        f"Blank: body {2 * half_x:.1f} x {2 * half_y:.1f}, lid {g['lid_len']:.1f} x {2 * lid_hy:.1f}.",
    ]):
        notes.append(f'<text x="{m}" y="{Y(base - 12 * i)}" font-size="6">{s}</text>')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}mm" height="{height:.0f}mm" viewBox="0 0 {width:.0f} {height:.0f}">
<rect width="100%" height="100%" fill="white"/>
<g id="cut" fill="none" stroke="black" stroke-width="0.4">{"".join(cut)}</g>
<g id="crease" fill="none" stroke="#1565c0" stroke-width="0.4" stroke-dasharray="4 2">{"".join(crease)}</g>
<g id="optional" fill="none" stroke="#c62828" stroke-width="0.4" stroke-dasharray="1.5 1.5">{"".join(opt)}</g>
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
