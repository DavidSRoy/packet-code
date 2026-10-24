#!/usr/bin/env python3
"""Make the box-lid sticker files (SVG per box, one PDF for all) and the layout JSON.

Sticker: 300 x 200 mm, for the 307.6 x 206.4 mm BX-006 lid.
- Centre: one ArUco DICT_4X4_50 tag, ID = box number. Black border 168 mm
  (28 mm cells). This is the far-range box ID (about 6-8 m on the B0322 camera).
- Corners: four AprilTag 36h11 tags, 40 mm (5 mm cells), IDs 4n .. 4n+3 for
  box n (top-left, top-right, bottom-right, bottom-left). These give the final
  position and yaw below about 1.3 m.

Lid frame (lid_layout.json): origin at the sticker centre, +x to the right,
+y to the top edge, +z up out of the lid, units metres. Corners are in OpenCV
order (TL, TR, BR, BL of the tag as printed).

Example:
  python3 lid_stickers.py --boxes 1-12 --out stickers
"""
import argparse
import json
import os

import cv2

W, H = 300.0, 200.0                      # sticker, mm
BIG_CELLS, BIG_CELL = 6, 28.0            # 4x4 data + 1-cell black border
BIG = BIG_CELLS * BIG_CELL               # 168 mm
BIG_X, BIG_Y = (W - BIG) / 2, (H - BIG) / 2
SMALL_CELLS, SMALL_CELL = 8, 5.0         # 6x6 data + border
SMALL = SMALL_CELLS * SMALL_CELL         # 40 mm
INSET = 10.0                             # sticker edge to small-tag black edge
CORNERS = [  # (x, y) of each small tag's top-left, in sticker mm (y down)
    (INSET, INSET), (W - INSET - SMALL, INSET),
    (W - INSET - SMALL, H - INSET - SMALL), (INSET, H - INSET - SMALL)]

ARUCO = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
APRIL = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)


def bits(d, tag_id, cells):
    img = d.generateImageMarker(tag_id, cells, borderBits=1)
    return [[img[r, c] < 128 for c in range(cells)] for r in range(cells)]


def tag_rects(d, tag_id, cells, cell, x0, y0):
    """Black rectangles of one tag, joined along rows: (x, y, w, h) mm."""
    out = []
    for r, row in enumerate(bits(d, tag_id, cells)):
        c = 0
        while c < cells:
            if row[c]:
                s = c
                while c < cells and row[c]:
                    c += 1
                out.append((x0 + s * cell, y0 + r * cell, (c - s) * cell, cell))
            else:
                c += 1
    return out


def corner_ids(box):
    return [4 * box + k for k in range(4)]


def layout(box):
    def quad(x, y, s):  # sticker mm (y down) -> lid metres (y up), OpenCV order
        pts = [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]
        return [[round((px - W / 2) / 1000, 4), round((H / 2 - py) / 1000, 4), 0.0]
                for px, py in pts]
    return {
        "box": box,
        "aruco_4x4_50": {"id": box, "size_m": BIG / 1000, "corners_m": quad(BIG_X, BIG_Y, BIG)},
        "apriltag_36h11": [{"id": i, "size_m": SMALL / 1000, "corners_m": quad(x, y, SMALL)}
                           for i, (x, y) in zip(corner_ids(box), CORNERS)],
    }


def shapes(box):
    """All marks of one sticker: list of ('rect', x, y, w, h) and ('text', ...)."""
    s = [("rect",) + r for r in tag_rects(ARUCO, box, BIG_CELLS, BIG_CELL, BIG_X, BIG_Y)]
    for i, (x, y) in zip(corner_ids(box), CORNERS):
        s += [("rect",) + r for r in tag_rects(APRIL, i, SMALL_CELLS, SMALL_CELL, x, y)]
    # Left strip: box label, read bottom-to-top. Right strip: print-scale check.
    s.append(("text", INSET + SMALL / 2, H / 2, f"BOX {box:02d}", 11.0, -90))
    bar_x, bar_y0, bar_len = W - INSET - SMALL / 2 + 6, H / 2 - 25, 50.0
    s.append(("rect", bar_x, bar_y0, 1.0, bar_len))
    for t in (bar_y0, bar_y0 + bar_len - 1.0):
        s.append(("rect", bar_x - 3, t, 7.0, 1.0))
    s.append(("text", bar_x - 7, H / 2, "BAR 50 mm  |  BIG TAG 168 mm", 3.2, -90))
    return s


def svg(box):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" '
           f'viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="#fff"/>',
           f'<rect x="0.1" y="0.1" width="{W-0.2}" height="{H-0.2}" fill="none" '
           f'stroke="#c8c8c8" stroke-width="0.2"/>', '<g fill="#000">']
    # All black cells in one path: no anti-alias seams between cells.
    d = "".join(f"M{x:g} {y:g}h{w:g}v{h:g}h{-w:g}z"
                for _, x, y, w, h in (sh for sh in shapes(box) if sh[0] == "rect"))
    out.append(f'<path d="{d}"/>')
    for sh in shapes(box):
        if sh[0] == "rect":
            continue
        else:
            _, x, y, txt, size, rot = sh
            out.append(f'<text x="{x:g}" y="{y:g}" font-family="Helvetica, Arial, sans-serif" '
                       f'font-weight="700" font-size="{size}" text-anchor="middle" '
                       f'dominant-baseline="central" transform="rotate({rot} {x:g} {y:g})">'
                       f'{txt}</text>')
    out += ["</g>", "</svg>"]
    return "\n".join(out)


def pdf(boxes, path):
    """Plain PDF, one 300 x 200 mm page per box, vector rectangles."""
    k = 72 / 25.4
    objs = {1: "<< /Type /Catalog /Pages 2 0 R >>",
            3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"}
    kids, n = [], 4
    for box in boxes:
        ops = ["1 1 1 rg 0 0 %.3f %.3f re f" % (W * k, H * k),
               "0.784 0.784 0.784 RG 0.567 w 0.28 0.28 %.3f %.3f re S" % (W * k - .57, H * k - .57),
               "0 0 0 rg"]
        texts = []
        for sh in shapes(box):
            if sh[0] == "rect":
                _, x, y, w, h = sh
                ops.append("%.3f %.3f %.3f %.3f re" % (x * k, (H - y - h) * k, w * k, h * k))
            else:
                _, x, y, txt, size, rot = sh
                fs = size * k
                tw = 0.6 * fs * len(txt)  # rough Helvetica-Bold width, for centring
                # rotate -90 in SVG (y down) = text reads bottom-to-top = +90 in PDF
                texts.append("BT /F1 %.2f Tf 0 1 -1 0 %.3f %.3f Tm (%s) Tj ET" % (
                    fs, (x + size * 0.35) * k, (H - y) * k - tw / 2, txt))
        ops.append("f")  # one fill for all cells: no seams
        ops += texts
        stream = "\n".join(ops)
        objs[n] = "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        objs[n + 1] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.3f %.3f] "
                       "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
                       % (W * k, H * k, n))
        kids.append(n + 1)
        n += 2
    objs[2] = "<< /Type /Pages /Kids [%s] /Count %d >>" % (
        " ".join(f"{i} 0 R" for i in kids), len(kids))
    body, offs = b"%PDF-1.4\n", {}
    for i in sorted(objs):
        offs[i] = len(body)
        body += f"{i} 0 obj\n{objs[i]}\nendobj\n".encode()
    xref = len(body)
    body += f"xref\n0 {n}\n0000000000 65535 f \n".encode()
    body += "".join(f"{offs[i]:010d} 00000 n \n" for i in range(1, n)).encode()
    body += f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    open(path, "wb").write(body)


def parse_boxes(s):
    a, _, b = s.partition("-")
    out = list(range(int(a), int(b or a) + 1))
    if not all(0 <= x <= 49 for x in out):
        raise SystemExit("box numbers must be 0-49 (DICT_4X4_50)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boxes", default="1-12", help="e.g. 1-12 or 7")
    ap.add_argument("--out", default="stickers")
    a = ap.parse_args()
    boxes = parse_boxes(a.boxes)
    os.makedirs(a.out, exist_ok=True)
    for b in boxes:
        with open(os.path.join(a.out, f"box_{b:02d}.svg"), "w") as f:
            f.write(svg(b))
    pdf(boxes, os.path.join(a.out, "lid_stickers.pdf"))
    with open(os.path.join(a.out, "lid_layout.json"), "w") as f:
        json.dump({"sticker_mm": [W, H], "frame": "origin sticker centre, +x right, +y top, "
                   "+z up, metres; corners TL,TR,BR,BL as printed",
                   "boxes": [layout(b) for b in boxes]}, f, indent=1)
    print(f"wrote {len(boxes)} stickers to {a.out}/")


if __name__ == "__main__":
    main()
