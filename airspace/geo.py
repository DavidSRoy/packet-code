"""Grid and geometry helpers for the ceiling map (numpy only)."""
import math
import struct
import zlib

import numpy as np

M_PER_DEG = 111_320.0
FT = 0.3048


class Grid:
    """Regular lat/lon grid. Row 0 is the north edge. Cells are about res_m square."""

    def __init__(self, south, west, north, east, res_m=20.0):
        self.s, self.w, self.n, self.e = float(south), float(west), float(north), float(east)
        self.res_m = float(res_m)
        self.lat0 = (self.s + self.n) / 2
        self.dlat = res_m / M_PER_DEG
        self.dlon = res_m / (M_PER_DEG * math.cos(math.radians(self.lat0)))
        self.rows = int(math.ceil((self.n - self.s) / self.dlat))
        self.cols = int(math.ceil((self.e - self.w) / self.dlon))
        self.n_edge = self.n                       # cell (0, 0) north-west corner
        self.s_edge = self.n - self.rows * self.dlat
        self.e_edge = self.w + self.cols * self.dlon

    @property
    def shape(self):
        return self.rows, self.cols

    def key(self):
        return f"{self.s:.4f}_{self.w:.4f}_{self.n:.4f}_{self.e:.4f}_{self.res_m:g}"

    def rc(self, lat, lon):
        """Fractional row, col of a point (cell centres at .5)."""
        return (self.n - lat) / self.dlat, (lon - self.w) / self.dlon

    def cell(self, lat, lon):
        r, c = self.rc(lat, lon)
        r, c = int(math.floor(r)), int(math.floor(c))
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return r, c
        return None

    def contains(self, lat, lon):
        return self.cell(lat, lon) is not None

    def lats(self):
        return self.n - (np.arange(self.rows) + 0.5) * self.dlat

    def lons(self):
        return self.w + (np.arange(self.cols) + 0.5) * self.dlon

    def cells_for_m(self, metres):
        return metres / self.res_m


def disk_offsets(radius_cells):
    r = int(math.ceil(radius_cells))
    out = []
    for dr in range(-r, r + 1):
        for dc in range(-r, r + 1):
            if dr * dr + dc * dc <= radius_cells * radius_cells:
                out.append((dr, dc))
    return out


def _shifted(a, dr, dc, fill):
    """a shifted so out[r, c] = a[r + dr, c + dc] (fill outside)."""
    out = np.full_like(a, fill)
    R, C = a.shape
    rs, re_ = max(0, -dr), min(R, R - dr)
    cs, ce = max(0, -dc), min(C, C - dc)
    if rs < re_ and cs < ce:
        out[rs:re_, cs:ce] = a[rs + dr:re_ + dr, cs + dc:ce + dc]
    return out


def disk_filter(a, radius_cells, op):
    """Max or min of a over a disk around each cell. op is np.maximum or np.minimum."""
    if radius_cells <= 0:
        return a.copy()
    if a.dtype == bool:
        fill = False if op is np.maximum else True
    else:
        fill = -np.inf if op is np.maximum else np.inf
    out = a.copy()
    for dr, dc in disk_offsets(radius_cells):
        if dr or dc:
            out = op(out, _shifted(a, dr, dc, fill))
    return out


def ring_bbox(ring):
    lats = [p[0] for p in ring]
    lons = [p[1] for p in ring]
    return min(lats), min(lons), max(lats), max(lons)


def fill_ring(grid, ring, out, value=True, combine=None):
    """Scanline fill of a polygon ring [(lat, lon), ...] into out (cells whose centre is inside).

    combine(old, value) -> new, default: set value."""
    if len(ring) < 3:
        return
    s, w, n, e = ring_bbox(ring)
    r0 = max(0, int(math.floor((grid.n - n) / grid.dlat)))
    r1 = min(grid.rows - 1, int(math.ceil((grid.n - s) / grid.dlat)))
    if r0 > r1:
        return
    pts = np.asarray(ring, dtype=float)
    y1, x1 = pts[:, 0], pts[:, 1]
    y2, x2 = np.roll(y1, -1), np.roll(x1, -1)
    lons = grid.lons()
    for r in range(r0, r1 + 1):
        y = grid.n - (r + 0.5) * grid.dlat
        cross = (y1 > y) != (y2 > y)
        if not cross.any():
            continue
        xs = np.sort(x1[cross] + (y - y1[cross]) * (x2[cross] - x1[cross]) / (y2[cross] - y1[cross]))
        for a, b in zip(xs[0::2], xs[1::2]):
            c0 = max(0, int(math.ceil((a - grid.w) / grid.dlon - 0.5)))
            c1 = min(grid.cols - 1, int(math.floor((b - grid.w) / grid.dlon - 0.5)))
            if c0 <= c1:
                if combine is None:
                    out[r, c0:c1 + 1] = value
                else:
                    out[r, c0:c1 + 1] = combine(out[r, c0:c1 + 1], value)


def point_in_ring(lat, lon, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        y1, x1 = ring[i]
        y2, x2 = ring[i - 1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def local_m(lat0, lon0, lat, lon):
    """North, east metres of (lat, lon) from (lat0, lon0)."""
    return (lat - lat0) * M_PER_DEG, (lon - lon0) * M_PER_DEG * math.cos(math.radians(lat0))


def dist_to_ring_m(lat, lon, ring):
    """Shortest distance (m) from a point to the edge of a ring."""
    best = math.inf
    pts = [local_m(lat, lon, p[0], p[1]) for p in ring]
    for i in range(len(pts)):
        (ay, ax), (by, bx) = pts[i - 1], pts[i]
        dy, dx = by - ay, bx - ax
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L2))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def ring_touches_disk(lat, lon, radius_m, ring):
    """True if a polygon ring overlaps a disk (centre inside or edge within radius)."""
    s, w, n, e = ring_bbox(ring)
    pad_lat = radius_m / M_PER_DEG
    pad_lon = radius_m / (M_PER_DEG * math.cos(math.radians(lat)))
    if not (s - pad_lat <= lat <= n + pad_lat and w - pad_lon <= lon <= e + pad_lon):
        return False
    return point_in_ring(lat, lon, ring) or dist_to_ring_m(lat, lon, ring) <= radius_m


def circle_ring(lat, lon, radius_m, n=48):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        out.append((lat + radius_m * math.cos(a) / M_PER_DEG,
                    lon + radius_m * math.sin(a) / (M_PER_DEG * math.cos(math.radians(lat)))))
    return out


def png_rgba(rgba):
    """Encode an (h, w, 4) uint8 array as PNG bytes."""
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[r].tobytes() for r in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def nearest_on_ring(lat, lon, ring):
    """(distance m, lat, lon) of the point on a ring's edge nearest to (lat, lon)."""
    best = (math.inf, None, None)
    k_lon = M_PER_DEG * math.cos(math.radians(lat))
    pts = [((p[0] - lat) * M_PER_DEG, (p[1] - lon) * k_lon) for p in ring]
    for i in range(len(pts)):
        (ay, ax), (by, bx) = pts[i - 1], pts[i]
        dy, dx = by - ay, bx - ax
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L2))
        py, px = ay + t * dy, ax + t * dx
        d = math.hypot(px, py)
        if d < best[0]:
            best = (d, lat + py / M_PER_DEG, lon + px / k_lon)
    return best
