"""Resumable FC log download through the Pi's shared link; never owns serial0.

On Pi: python log_download.py udpout:127.0.0.1:14650 2000000 ~/flight-data/bin --latest 0
Requests bounded blocks only with a fresh disarmed FC heartbeat. Pauses while armed.
Undated logs are re-read on process restart because their identity is ambiguous.
Incomplete files remain .part; only complete files become .BIN (with SHA256 manifest).
"""
import os
os.environ.setdefault("MAVLINK20", "1")
import argparse
import hashlib
import json
import time
from pathlib import Path
from pymavlink import mavutil

CHUNK = 90
WINDOW = 4500

class Link:
    def __init__(self, m):
        self.m = m
        self.hb = 0
        self.armed = True
        self.next_hb = 0

    def receive(self, timeout=0.1):
        now = time.monotonic()
        if now >= self.next_hb:
            self.m.mav.heartbeat_send(6, 8, 0, 0, 4)
            self.next_hb = now + 1
        msg = self.m.recv_match(blocking=True, timeout=timeout)
        if msg and msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
            if msg.get_type() == 'HEARTBEAT':
                was_safe = self.safe()
                self.hb = time.monotonic()
                self.armed = bool(msg.base_mode & 128)
                if was_safe and self.armed:
                    self.m.mav.log_request_end_send(1, 1)
            return msg
        return None

    def safe(self):
        return not self.armed and time.monotonic() - self.hb < 2

    def wait_safe(self):
        while not self.safe():
            self.receive()


def download(link, lid, size, stamp, out):
    dest = out / f'{lid:08d}.BIN'
    manifest = dest.with_suffix('.json')
    identity = {'id': lid, 'size': size, 'time_utc': stamp}
    dated = stamp > 315532800  # FCs without an RTC often report 1980 for every log.
    if dated and dest.exists() and manifest.exists():
        old = json.loads(manifest.read_text())
        if all(old.get(k) == v for k, v in identity.items()) and dest.stat().st_size == size:
            if hashlib.sha256(dest.read_bytes()).hexdigest() == old.get('sha256'):
                print(f'log {lid}: verified existing', flush=True)
                return
    part = dest.with_suffix('.part')
    meta = dest.with_suffix('.part.json')
    if not dated or not meta.exists() or json.loads(meta.read_text()) != identity:
        part.write_bytes(b'')
        meta.write_text(json.dumps(identity))
    offset = part.stat().st_size if part.exists() else 0
    if offset > size or (offset != size and offset % CHUNK):
        offset = 0
        part.write_bytes(b'')
    started = time.monotonic()
    with part.open('ab') as f:
        while offset < size:
            link.wait_safe()
            count = min(WINDOW, size-offset)
            pieces = {}
            for attempt in range(15):
                link.wait_safe()
                link.m.mav.log_request_data_send(1, 1, lid, offset, count)
                deadline = time.monotonic() + 1.5
                while time.monotonic() < deadline and link.safe():
                    d = link.receive()
                    if d and d.get_type() == 'LOG_DATA' and d.id == lid:
                        expected = min(CHUNK, offset+count-d.ofs)
                        if offset <= d.ofs < offset+count and (d.ofs-offset) % CHUNK == 0 and d.count == expected:
                            pieces[d.ofs] = bytes(d.data[:d.count])
                    if sum(map(len, pieces.values())) == count:
                        break
                if sum(map(len, pieces.values())) == count:
                    break
            else:
                raise RuntimeError(f'log {lid}: block at {offset}/{size} unavailable; retained .part')
            for pos in sorted(pieces):
                f.write(pieces[pos])
            f.flush()
            offset += count
            # Yield shared bandwidth even if the FC delivered a block immediately.
            until = time.monotonic() + 0.15
            while time.monotonic() < until:
                link.receive(0.02)
            if offset % (WINDOW*100) == 0:
                print(f'log {lid}: {offset}/{size}', flush=True)
    part.replace(dest)
    identity['sha256'] = hashlib.sha256(dest.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(identity, indent=2))
    meta.unlink(missing_ok=True)
    print(f'log {lid}: COMPLETE {size} bytes in {time.monotonic()-started:.1f}s', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('port')
    ap.add_argument('baud', type=int)
    ap.add_argument('out', type=Path)
    ap.add_argument('--latest', type=int, default=1, help='0 = all logs')
    ap.add_argument('--since', type=int, default=0, help='UTC Unix timestamp; include undated logs')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    m = mavutil.mavlink_connection(args.port, baud=args.baud, source_system=246, source_component=196)
    link = Link(m)
    try:
        link.wait_safe()
        entries = {}
        total = None
        for _ in range(3):
            link.wait_safe()
            m.mav.log_request_list_send(1, 1, 0, 65535)
            end = time.monotonic()+5
            while time.monotonic() < end and link.safe():
                e = link.receive()
                if e and e.get_type() == 'LOG_ENTRY':
                    total = e.num_logs
                    entries[e.id] = (e.size, e.time_utc)
                    if len(entries) >= e.num_logs:
                        break
            if total is not None and len(entries) >= total:
                break
        if total is None or len(entries) != total:
            raise RuntimeError('incomplete FC log inventory; retry before selecting logs')
        print('inventory:', json.dumps(entries), flush=True)
        ids = [lid for lid in sorted(entries) if entries[lid][0] and (not entries[lid][1] or entries[lid][1] >= args.since)]
        if args.latest:
            ids = ids[-args.latest:]
        failures = []
        for lid in reversed(ids):
            try:
                download(link, lid, *entries[lid], args.out)
            except RuntimeError as exc:
                print(str(exc), flush=True)
                failures.append(lid)
        if failures:
            raise SystemExit(f'incomplete logs: {failures}')
    finally:
        m.mav.log_request_end_send(1, 1)
        m.close()

if __name__ == '__main__':
    main()
